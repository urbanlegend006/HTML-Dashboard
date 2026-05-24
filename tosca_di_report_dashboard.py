import sqlite3
import json
import os
from collections import Counter
import re
import html
import hashlib
import time

__version__ = "4.0"


def inline_diff(source, target):
    """Character-level diff highlighting using LCS. Returns (src_html, tgt_html) with <mark> tags."""
    if source is None or target is None:
        return (html.escape(str(source)) if source else "", html.escape(str(target)) if target else "")
    s = str(source)
    t = str(target)
    if s == t:
        return (html.escape(s), html.escape(t))
    # LCS table
    m, n = len(s), len(t)
    if m > 500 or n > 500:  # Skip diff for very long strings
        return (html.escape(s), html.escape(t))
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s[i-1] == t[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    # Backtrack to find LCS
    lcs = []
    i, j = m, n
    while i > 0 and j > 0:
        if s[i-1] == t[j-1]:
            lcs.append((i-1, j-1))
            i -= 1
            j -= 1
        elif dp[i-1][j] > dp[i][j-1]:
            i -= 1
        else:
            j -= 1
    lcs.reverse()
    # Build source HTML
    src_parts = []
    prev_si = 0
    lcs_s_indices = set(p[0] for p in lcs)
    run_del = []
    for ci in range(m):
        if ci in lcs_s_indices:
            if run_del:
                src_parts.append('<mark class="diff-del">' + html.escape(''.join(run_del)) + '</mark>')
                run_del = []
            src_parts.append(html.escape(s[ci]))
        else:
            run_del.append(s[ci])
    if run_del:
        src_parts.append('<mark class="diff-del">' + html.escape(''.join(run_del)) + '</mark>')
    # Build target HTML
    tgt_parts = []
    lcs_t_indices = set(p[1] for p in lcs)
    run_add = []
    for ci in range(n):
        if ci in lcs_t_indices:
            if run_add:
                tgt_parts.append('<mark class="diff-add">' + html.escape(''.join(run_add)) + '</mark>')
                run_add = []
            tgt_parts.append(html.escape(t[ci]))
        else:
            run_add.append(t[ci])
    if run_add:
        tgt_parts.append('<mark class="diff-add">' + html.escape(''.join(run_add)) + '</mark>')
    return (''.join(src_parts), ''.join(tgt_parts))


def highlight_sql(sql_text):
    """Add syntax highlighting spans to SQL text. Returns HTML string."""
    if not sql_text or sql_text == '0':
        return html.escape(str(sql_text))
    text = str(sql_text)
    # Tokenize: preserve strings, comments, and whitespace
    tokens = []
    i = 0
    while i < len(text):
        # Single-line comment
        if text[i:i+2] == '--':
            end = text.find('\n', i)
            if end == -1: end = len(text)
            tokens.append(('comment', text[i:end]))
            i = end
        # Multi-line comment
        elif text[i:i+2] == '/*':
            end = text.find('*/', i)
            if end == -1: end = len(text)
            else: end += 2
            tokens.append(('comment', text[i:end]))
            i = end
        # String literal
        elif text[i] == "'":
            j = i + 1
            while j < len(text):
                if text[j] == "'":
                    if j + 1 < len(text) and text[j+1] == "'":
                        j += 2
                    else:
                        j += 1
                        break
                else:
                    j += 1
            tokens.append(('string', text[i:j]))
            i = j
        # Word
        elif text[i].isalpha() or text[i] == '_':
            j = i
            while j < len(text) and (text[j].isalnum() or text[j] == '_'):
                j += 1
            tokens.append(('word', text[i:j]))
            i = j
        # Number
        elif text[i].isdigit() or (text[i] == '.' and i + 1 < len(text) and text[i+1].isdigit()):
            j = i
            while j < len(text) and (text[j].isdigit() or text[j] == '.'):
                j += 1
            tokens.append(('number', text[i:j]))
            i = j
        else:
            tokens.append(('other', text[i]))
            i += 1
    # Classify words
    statements = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'MERGE', 'WITH', 'DECLARE', 'SET', 'EXEC', 'EXECUTE'}
    clauses = {'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'ON', 'ORDER', 'BY', 'GROUP', 'HAVING', 'LIMIT', 'UNION', 'ALL', 'DISTINCT', 'INTO', 'VALUES', 'TOP', 'OFFSET', 'FETCH', 'NEXT', 'ROWS', 'ONLY'}
    operators = {'AND', 'OR', 'NOT', 'IN', 'BETWEEN', 'LIKE', 'IS', 'NULL', 'AS', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'EXISTS', 'ASC', 'DESC', 'OVER', 'PARTITION', 'NULLS', 'FIRST', 'LAST'}
    functions = {'COUNT', 'SUM', 'MAX', 'MIN', 'AVG', 'COALESCE', 'CAST', 'CONVERT', 'ISNULL', 'NVL', 'TRIM', 'LTRIM', 'RTRIM', 'UPPER', 'LOWER', 'SUBSTRING', 'LEN', 'LENGTH', 'REPLACE', 'CONCAT', 'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'LAG', 'LEAD', 'GETDATE', 'SYSDATE', 'DATEADD', 'DATEDIFF', 'TO_DATE', 'TO_CHAR', 'TO_NUMBER', 'DECODE', 'NVL2', 'LISTAGG', 'ROUND', 'FLOOR', 'CEIL', 'ABS', 'MOD'}
    parts = []
    for ttype, tval in tokens:
        if ttype == 'comment':
            parts.append(f'<span class="sql-comment">{html.escape(tval)}</span>')
        elif ttype == 'string':
            parts.append(f'<span class="sql-string">{html.escape(tval)}</span>')
        elif ttype == 'number':
            parts.append(f'<span class="sql-number">{html.escape(tval)}</span>')
        elif ttype == 'word':
            upper = tval.upper()
            if upper in statements:
                parts.append(f'<span class="sql-keyword">{html.escape(tval)}</span>')
            elif upper in clauses:
                parts.append(f'<span class="sql-clause">{html.escape(tval)}</span>')
            elif upper in operators:
                parts.append(f'<span class="sql-operator">{html.escape(tval)}</span>')
            elif upper in functions:
                parts.append(f'<span class="sql-function">{html.escape(tval)}</span>')
            else:
                parts.append(html.escape(tval))
        else:
            parts.append(html.escape(tval))
    return ''.join(parts)


def generate_sparkline_svg(value, seed_extra=''):
    """Generate a decorative SVG sparkline based on a value hash."""
    h = hashlib.md5(f"{value}{seed_extra}".encode()).hexdigest()
    points = [int(h[i:i+2], 16) % 24 + 4 for i in range(0, 20, 2)]
    coords = ' '.join(f"{i * 10},{p}" for i, p in enumerate(points))
    return f'<svg class="sparkline-svg" viewBox="0 0 90 32" preserveAspectRatio="none" fill="none" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="spk{h[:6]}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" class="sparkline-stop1"/><stop offset="100%" class="sparkline-stop2"/></linearGradient></defs><polyline points="{coords}" class="sparkline-line" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polygon points="0,32 {coords} 90,32" fill="url(#spk{h[:6]})" class="sparkline-fill"/></svg>'


ERROR_TYPES = [
    "Source Value is NULL",
    "Target Value is NULL",
    "Null Equivalent Mismatch",
    "Duplicate Value Mismatch",
    "Sorting Issue",
    "Whitespace Mismatch",
    "Case Sensitivity Mismatch",
    "Type Coercion / Formatting",
    "Boolean Format Mismatch",
    "Encoding / Special Char Mismatch",
    "Precision / Rounding",
    "Data Truncation",
    "Date/Timestamp Mismatch",
    "Numeric Data Mismatch",
    "String Data Mismatch"
]

COLOR_MAP = {
    "Source Value is NULL": "#a855f7", 
    "Target Value is NULL": "#ec4899", 
    "Null Equivalent Mismatch": "#d946ef", 
    "Duplicate Value Mismatch": "#f43f5e", 
    "Sorting Issue": "#6366f1", 
    "Whitespace Mismatch": "#84cc16", 
    "Case Sensitivity Mismatch": "#0ea5e9", 
    "Type Coercion / Formatting": "#8b5cf6", 
    "Boolean Format Mismatch": "#10b981", 
    "Encoding / Special Char Mismatch": "#f59e0b", 
    "Precision / Rounding": "#14b8a6", 
    "Data Truncation": "#ef4444", 
    "Date/Timestamp Mismatch": "#eab308", 
    "Numeric Data Mismatch": "#06b6d4", 
    "String Data Mismatch": "#f97316"
}

def is_date_like(val):
    date_patterns = [
        r'\d{4}-\d{2}-\d{2}',
        r'\d{2}/\d{2}/\d{4}',
        r'\d{2}-\d{2}-\d{4}'
    ]
    return any(re.match(p, str(val)) for p in date_patterns)

def format_val_html(val, placeholder=""):
    if val is None or str(val) == '' or str(val).lower() == 'none':
        return ""
    return html.escape(str(val))

def generate_unified_dashboard(db_path, output_html="output/tosca_enterprise_report.html", row_keys=None):
    start_time = time.time()
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ==========================================
    # 1. RETRIEVE GLOBAL METRICS
    # ==========================================
    def get_meta(key):
        cursor.execute("SELECT Value FROM Metadata WHERE Key = ?", (key,))
        res = cursor.fetchone()
        return res[0] if res else "0"

    report_date = get_meta('$.reportInfo.createdAt')
    total_rows = int(get_meta('$.reportInfo.comparisonOverview.sourceRowsProcessed'))
    matched_count = int(get_meta('$.reportInfo.comparisonOverview.matchedRowsCount'))
    diff_row_count = int(get_meta('$.reportInfo.comparisonOverview.rowsWithDifferences'))
    pass_rate = round((matched_count / total_rows) * 100, 2) if total_rows > 0 else 0

    source_type = get_meta('$.reportInfo.source.type')
    source_desc = get_meta('$.reportInfo.source.description')
    source_sql = get_meta('$.reportInfo.source.sql')
    target_type = get_meta('$.reportInfo.target.type')
    target_desc = get_meta('$.reportInfo.target.description')
    target_sql = get_meta('$.reportInfo.target.sql')

    # ==========================================
    # 2. COLUMN MAPPING
    # ==========================================
    cursor.execute("SELECT ColumnId, ColumnName FROM ColumnNames WHERE TableName='Differences'")
    col_map = {str(row[0]): row[1] for row in cursor.fetchall()}

    # ==========================================
    # 2b. ROW-KEY COLUMNS
    # ==========================================
    if row_keys is None:
        cursor.execute("SELECT RowKey FROM Differences WHERE RowKey IS NOT NULL LIMIT 1")
        sample_row = cursor.fetchone()
        if sample_row and sample_row[0]:
            num_cols = str(sample_row[0]).count('|') + 1
            row_key_columns = [f"col{i+1}" for i in range(num_cols)]
        else:
            row_key_columns = []
    else:
        row_key_columns = row_keys

    # ==========================================
    # 3. ADVANCED ANALYSIS (LOGIC + SORTING)
    # ==========================================
    matrix = {}
    samples = {}
    
    cursor.execute("SELECT * FROM Differences ORDER BY RowKey, System")
    all_diffs = cursor.fetchall()
    col_desc = [d[0] for d in cursor.description]
    
    # Group by RowKey to compare sets of records
    row_groups = {}
    for r in all_diffs:
        rk = r[col_desc.index('RowKey')]
        if rk not in row_groups: row_groups[rk] = {'0': [], '1': []}
        row_groups[rk][str(r[col_desc.index('System')])].append(r)

    def get_mismatch_type(s_val, t_val):
        s_str = str(s_val) if s_val is not None else ""
        t_str = str(t_val) if t_val is not None else ""
        s_lower = s_str.lower()
        t_lower = t_str.lower()
        
        s_is_null = s_val is None or s_lower in ['none', 'null', '']
        t_is_null = t_val is None or t_lower in ['none', 'null', '']
        
        if s_is_null and not t_is_null:
            if t_lower in ['n/a', 'na', 'unknown', '0', '-1']: return "Null Equivalent Mismatch"
            return "Source Value is NULL"
        if t_is_null and not s_is_null:
            if s_lower in ['n/a', 'na', 'unknown', '0', '-1']: return "Null Equivalent Mismatch"
            return "Target Value is NULL"
        if s_is_null and t_is_null:
            return None

        if s_str.strip() == t_str.strip(): return "Whitespace Mismatch"
        if s_lower == t_lower: return "Case Sensitivity Mismatch"
            
        s_clean = re.sub(r'[^\x00-\x7F]+', '', s_str)
        t_clean = re.sub(r'[^\x00-\x7F]+', '', t_str)
        if s_clean == t_clean and s_clean != "": return "Encoding / Special Char Mismatch"

        s_is_num = False; t_is_num = False; s_float = None; t_float = None
        try: s_float = float(s_str.replace(',', '')); s_is_num = True
        except: pass
        try: t_float = float(t_str.replace(',', '')); t_is_num = True
        except: pass

        if s_is_num and t_is_num:
            if s_float == t_float: return "Type Coercion / Formatting"
            s_decimals = len(s_str.split('.')[-1]) if '.' in s_str else 0
            t_decimals = len(t_str.split('.')[-1]) if '.' in t_str else 0
            if s_decimals != t_decimals:
                min_dec = min(s_decimals, t_decimals)
                if round(s_float, min_dec) == round(t_float, min_dec): return "Precision / Rounding"
                    
        bool_vals = ['true', 'false', 'y', 'n', 'yes', 'no', '1', '0']
        if s_lower in bool_vals and t_lower in bool_vals: return "Boolean Format Mismatch"
            
        if len(s_str) > 0 and len(t_str) > 0:
            if (s_str.startswith(t_str) or t_str.startswith(s_str)) and abs(len(s_str) - len(t_str)) > 0:
                return "Data Truncation"

        if is_date_like(s_str) and is_date_like(t_str): return "Date/Timestamp Mismatch"
        if s_is_num and t_is_num: return "Numeric Data Mismatch"
        return "String Data Mismatch"

    for rk, systems in row_groups.items():
        src_rows = systems['0']
        tgt_rows = systems['1']
        
        # Get all affected columns for this group
        affected_indices = set()
        for r in src_rows + tgt_rows:
            idx_str = r[col_desc.index('Affected Column Indexes')]
            if idx_str: affected_indices.update(str(idx_str).split(','))

        for idx in affected_indices:
            col_name = col_map.get(idx, f"Col_{idx}")
            if col_name not in matrix:
                matrix[col_name] = {k: 0 for k in ERROR_TYPES}
                samples[col_name] = {k: [] for k in matrix[col_name].keys()}
            
            try:
                v_idx = col_desc.index(idx)
            except ValueError:
                continue

            s_vals = [str(r[v_idx]) if r[v_idx] is not None else None for r in src_rows]
            t_vals = [str(r[v_idx]) if r[v_idx] is not None else None for r in tgt_rows]

            # DETECT SORTING ISSUES
            if Counter(s_vals) == Counter(t_vals) and len(s_vals) > 1:
                mtype = "Sorting Issue"
                # Add the number of pairs (one side) to avoid doubling the issue count
                matrix[col_name][mtype] += len(s_vals)
                if len(samples[col_name][mtype]) < 5:
                    samples[col_name][mtype].append({
                        "row": rk, 
                        "src": " | ".join([v if v is not None else "[NULL]" for v in s_vals]), 
                        "tgt": " | ".join([v if v is not None else "[NULL]" for v in t_vals])
                    })
            else:
                # Standard Pairwise comparison
                for i in range(max(len(s_vals), len(t_vals))):
                    sv = s_vals[i] if i < len(s_vals) else None
                    tv = t_vals[i] if i < len(t_vals) else None
                    if sv != tv:
                        if i >= min(len(s_vals), len(t_vals)):
                            mtype = "Duplicate Value Mismatch"
                        else:
                            mtype = get_mismatch_type(sv, tv)
                        if mtype is not None:
                            matrix[col_name][mtype] += 1
                            if len(samples[col_name][mtype]) < 5:
                                samples[col_name][mtype].append({"row": rk, "src": sv, "tgt": tv})

    # ==========================================
    # 3b. UNMATCHED & INVALID DATA EXTRACTION
    # ==========================================
    unmatched_src_rows = []
    unmatched_src_cols = []
    try:
        cursor.execute("SELECT ColumnId, ColumnName FROM ColumnNames WHERE TableName='UnmatchedSource'")
        unmatched_src_col_map = {str(row[0]): row[1] for row in cursor.fetchall()}
        cursor.execute("SELECT * FROM UnmatchedSource LIMIT 50")
        unmatched_src_raw = cursor.fetchall()
        unmatched_src_desc = [d[0] for d in cursor.description]
        unmatched_src_cols = [unmatched_src_col_map.get(str(col), str(col)) for col in unmatched_src_desc]
        unmatched_src_rows = [list(r) for r in unmatched_src_raw]
    except Exception as e:
        print(f"Error fetching UnmatchedSource: {e}")

    unmatched_tgt_rows = []
    unmatched_tgt_cols = []
    try:
        cursor.execute("SELECT ColumnId, ColumnName FROM ColumnNames WHERE TableName='UnmatchedTarget'")
        unmatched_tgt_col_map = {str(row[0]): row[1] for row in cursor.fetchall()}
        cursor.execute("SELECT * FROM UnmatchedTarget LIMIT 50")
        unmatched_tgt_raw = cursor.fetchall()
        unmatched_tgt_desc = [d[0] for d in cursor.description]
        unmatched_tgt_cols = [unmatched_tgt_col_map.get(str(col), str(col)) for col in unmatched_tgt_desc]
        unmatched_tgt_rows = [list(r) for r in unmatched_tgt_raw]
    except Exception as e:
        print(f"Error fetching UnmatchedTarget: {e}")

    invalid_src_rows = []
    invalid_src_cols = []
    try:
        cursor.execute("SELECT * FROM InvalidSource LIMIT 50")
        invalid_src_raw = cursor.fetchall()
        invalid_src_cols = [d[0] for d in cursor.description]
        invalid_src_rows = [list(r) for r in invalid_src_raw]
    except Exception as e:
        print(f"Error fetching InvalidSource: {e}")

    invalid_tgt_rows = []
    invalid_tgt_cols = []
    try:
        cursor.execute("SELECT * FROM InvalidTarget LIMIT 50")
        invalid_tgt_raw = cursor.fetchall()
        invalid_tgt_cols = [d[0] for d in cursor.description]
        invalid_tgt_rows = [list(r) for r in invalid_tgt_raw]
    except Exception as e:
        print(f"Error fetching InvalidTarget: {e}")

    unmatched_src_json = json.dumps({"columns": unmatched_src_cols, "rows": unmatched_src_rows})
    unmatched_tgt_json = json.dumps({"columns": unmatched_tgt_cols, "rows": unmatched_tgt_rows})
    invalid_src_json = json.dumps({"columns": invalid_src_cols, "rows": invalid_src_rows})
    invalid_tgt_json = json.dumps({"columns": invalid_tgt_cols, "rows": invalid_tgt_rows})

    try:
        src_not_found = int(get_meta('$.reportInfo.comparisonOverview.sourceRowsNotFound'))
    except:
        src_not_found = 0
    try:
        tgt_not_found = int(get_meta('$.reportInfo.comparisonOverview.targetRowsNotFound'))
    except:
        tgt_not_found = 0
    try:
        invalid_src_count = int(get_meta('$.reportInfo.comparisonOverview.invalidSourceRows'))
    except:
        invalid_src_count = 0
    try:
        invalid_tgt_count = int(get_meta('$.reportInfo.comparisonOverview.invalidTargetRows'))
    except:
        invalid_tgt_count = 0

    # ==========================================
    # 4. DATA PREP FOR UI & CHARTS
    # ==========================================
    sorted_matrix = sorted([{"Name": k, **v, "Total": sum(v.values())} for k, v in matrix.items()], key=lambda x: x['Total'], reverse=True)
    
    # Bar Chart Data
    bar_chart_labels = [r['Name'] for r in sorted_matrix[:5]]
    bar_chart_values = [r['Total'] for r in sorted_matrix[:5]]

    # Data Health Calculations
    match_pct = round((matched_count / total_rows) * 100, 1) if total_rows > 0 else 0
    diff_pct = round((diff_row_count / total_rows) * 100, 1) if total_rows > 0 else 0
    missing_pct = round(100 - match_pct - diff_pct, 1) if total_rows > 0 else 0
    if missing_pct < 0: missing_pct = 0

    # ==========================================
    # 4b. NEW KPIs & GRADE (v3.0)
    # ==========================================
    affected_columns = len(sorted_matrix)
    critical_fields = sum(1 for r in sorted_matrix if r['Total'] > 1000)
    warning_fields = sum(1 for r in sorted_matrix if 100 < r['Total'] <= 1000)
    info_fields = sum(1 for r in sorted_matrix if r['Total'] <= 100)
    total_issues_all = sum(r['Total'] for r in sorted_matrix)
    total_null_issues = sum(r.get('Source Value is NULL', 0) + r.get('Target Value is NULL', 0) for r in sorted_matrix)
    null_rate = round((total_null_issues / total_issues_all) * 100, 1) if total_issues_all > 0 else 0

    # Dominant error type
    error_type_keys = ERROR_TYPES
    error_type_totals = {t: sum(r.get(t, 0) for r in sorted_matrix) for t in error_type_keys}
    dominant_error = max(error_type_totals, key=error_type_totals.get) if error_type_totals else 'N/A'
    dominant_error_short = dominant_error.replace('Data ', '').replace('Value is ', '')

    # Dynamic Grade Badge
    if pass_rate > 95:
        grade, grade_color_text, grade_color_bg, grade_color_border = 'A+', '#15803d', 'rgba(22,163,74,0.15)', 'rgba(22,163,74,0.4)'
    elif pass_rate > 90:
        grade, grade_color_text, grade_color_bg, grade_color_border = 'A', '#16a34a', 'rgba(74,222,128,0.15)', 'rgba(74,222,128,0.4)'
    elif pass_rate > 85:
        grade, grade_color_text, grade_color_bg, grade_color_border = 'B', '#d97706', 'rgba(217,119,6,0.15)', 'rgba(217,119,6,0.4)'
    elif pass_rate > 80:
        grade, grade_color_text, grade_color_bg, grade_color_border = 'C', '#ca8a04', 'rgba(250,204,21,0.15)', 'rgba(250,204,21,0.4)'
    else:
        grade, grade_color_text, grade_color_bg, grade_color_border = 'D', '#dc2626', 'rgba(239,68,68,0.15)', 'rgba(239,68,68,0.4)'

    # Error Distribution Chart Data (for horizontal stacked bar)
    err_dist_labels = [r['Name'] for r in sorted_matrix]
    err_dist_data = {t: [r[t] for r in sorted_matrix] for t in ERROR_TYPES}

    # ==========================================
    # 5. HTML GENERATION
    # ==========================================
    # Pre-compute column totals for the sticky footer
    total_diffs = sum(r['Total'] for r in sorted_matrix)
    col_totals_html = "".join(
        f'<td class="px-2 py-3 text-center border-l border-slate-200/50 dark:border-slate-700/50">{sum(r[t] for r in sorted_matrix):,}</td>'
        for t in ERROR_TYPES
    )

    # Pre-compute Row-Key column badges HTML
    if row_key_columns:
        colors = [
            'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800/30',
            'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800/30',
            'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800/30',
            'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800/30'
        ]
        row_key_badges_html = ''.join(
            f'<span class="inline-flex items-center px-2.5 py-1 rounded-lg text-[11px] font-bold font-mono border shadow-sm mr-1.5 {colors[i % len(colors)]}">{col}</span>'
            for i, col in enumerate(row_key_columns)
        )
    else:
        row_key_badges_html = '<span class="text-[11px] text-slate-500 dark:text-slate-400 italic">Not detected</span>'

    table_body = ""
    for idx_r, r in enumerate(sorted_matrix):
        # Severity Badge & Backgrounds
        total = r['Total']
        if total > 1000:
            severity_badge = f'<span class="flex items-center justify-end gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]"></span><span class="text-red-700 dark:text-red-400 font-bold text-[11px]">Critical ({total:,})</span></span>'
            row_bg = "bg-red-100/60 hover:bg-red-100/80 dark:bg-red-900/10 dark:hover:bg-red-900/20"
        elif total > 100:
            severity_badge = f'<span class="flex items-center justify-end gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.5)]"></span><span class="text-yellow-700 dark:text-yellow-400 font-bold text-[11px]">Warning ({total:,})</span></span>'
            row_bg = "bg-yellow-100/60 hover:bg-yellow-100/80 dark:bg-yellow-900/10 dark:hover:bg-yellow-900/20"
        else:
            severity_badge = f'<span class="flex items-center justify-end gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span><span class="text-slate-600 dark:text-slate-400 font-bold text-[11px]">Info ({total:,})</span></span>'
            row_bg = "bg-white/50 hover:bg-slate-100 dark:bg-[#161b22]/50 dark:hover:bg-slate-800/50"

        # Accordion Samples HTML
        samples_html = ""
        for issue_type, smps in samples[r['Name']].items():
            if smps:
                headers = "<th class='pb-2 text-slate-500 dark:text-slate-400 font-semibold'>Row-key</th><th class='pb-2 text-slate-500 dark:text-slate-400 font-semibold'>Source Value</th><th class='pb-2 text-slate-500 dark:text-slate-400 font-semibold'>Target Value</th>" if issue_type != "Sorting Issue" else "<th class='pb-2 text-slate-500 dark:text-slate-400 font-semibold'>Row-key</th><th class='pb-2 text-slate-500 dark:text-slate-400 font-semibold'>Source Collection</th><th class='pb-2 text-slate-500 dark:text-slate-400 font-semibold'>Target Collection</th>"
                placeholder = "[MISSING]" if issue_type == "Duplicate Value Mismatch" else "[NULL]"
                def format_row_key(raw_key):
                    parts = raw_key.split('|')
                    colors = ['bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
                              'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300',
                              'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300',
                              'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300']
                    chips = ''.join(
                        f'<span class="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold {colors[i % len(colors)]} mr-1 mb-1.5">{html.escape(p) if p.strip() else "—"}</span>'
                        for i, p in enumerate(parts)
                    )
                    return chips
                smps_list = ""
                for s in smps:
                    src_val = s['src']
                    tgt_val = s['tgt']
                    if src_val is not None and tgt_val is not None and str(src_val).lower() not in ('none', '') and str(tgt_val).lower() not in ('none', ''):
                        src_html, tgt_html = inline_diff(src_val, tgt_val)
                    else:
                        src_html = format_val_html(src_val, placeholder)
                        tgt_html = format_val_html(tgt_val, placeholder)
                    smps_list += f"<tr class='border-t border-slate-100 dark:border-slate-800/50'><td class='py-3 font-mono text-[11px] text-slate-500 dark:text-slate-400 whitespace-normal break-words max-w-md' title='{s['row']}'>{format_row_key(s['row'])}</td><td class='py-3 text-red-500 dark:text-red-400 font-medium text-xs whitespace-normal break-words'>{src_html}</td><td class='py-3 text-green-600 dark:text-green-400 font-medium text-xs whitespace-normal break-words'>{tgt_html}</td></tr>"
                
                samples_html += f"""
                <div class="mb-4 bg-slate-50 dark:bg-slate-800/45 p-5 rounded-2xl border border-slate-100 dark:border-slate-800/50 shadow-inner">
                    <h4 class="text-sm font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wide mb-3 flex items-center gap-2">
                        <span class="w-1.5 h-1.5 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.5)]"></span>{issue_type}
                    </h4>
                    <table class="w-full text-left table-fixed">
                        <colgroup>
                            <col class="w-[55%]">
                            <col class="w-[22.5%]">
                            <col class="w-[22.5%]">
                        </colgroup>
                        <thead><tr class="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">{headers}</tr></thead>
                        <tbody>{smps_list}</tbody>
                    </table>
                </div>"""

        if not samples_html:
            samples_html = "<div class='text-slate-500 dark:text-slate-400 italic text-xs py-4 text-center bg-slate-50 dark:bg-slate-800/45 rounded-2xl'>No samples available.</div>"

        safe_id = f"acc-{idx_r}"

        # Matrix Row
        table_body += f"""
        <tr class="{row_bg} border-b border-slate-100 dark:border-slate-800/80 transition-all duration-200 cursor-pointer matrix-row group" onclick="toggleAccordion('{safe_id}')">
            <td class="px-4 py-3 font-bold text-slate-800 dark:text-slate-200 text-xs col-name flex items-center gap-2 sticky left-0 z-10 glass shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)]">
                <div class="w-5 h-5 shrink-0 rounded flex items-center justify-center bg-white dark:bg-slate-800 shadow-sm border border-slate-200 dark:border-slate-700 text-slate-400 transition-transform group-hover:scale-110">
                    <span class="text-[11px] transition-transform duration-300">▶</span>
                </div>
                <span class="truncate w-52" title="{r['Name']}">{r['Name']}</span>
            </td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Source Value is NULL'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Source Value is NULL']}">{r['Source Value is NULL']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Target Value is NULL'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Target Value is NULL']}">{r['Target Value is NULL']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Null Equivalent Mismatch'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Null Equivalent Mismatch']}">{r['Null Equivalent Mismatch']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Duplicate Value Mismatch'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Duplicate Value Mismatch']}">{r['Duplicate Value Mismatch']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Sorting Issue'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Sorting Issue']}">{r['Sorting Issue']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Whitespace Mismatch'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Whitespace Mismatch']}">{r['Whitespace Mismatch']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Case Sensitivity Mismatch'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Case Sensitivity Mismatch']}">{r['Case Sensitivity Mismatch']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Type Coercion / Formatting'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Type Coercion / Formatting']}">{r['Type Coercion / Formatting']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Boolean Format Mismatch'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Boolean Format Mismatch']}">{r['Boolean Format Mismatch']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Encoding / Special Char Mismatch'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Encoding / Special Char Mismatch']}">{r['Encoding / Special Char Mismatch']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Precision / Rounding'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Precision / Rounding']}">{r['Precision / Rounding']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Data Truncation'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Data Truncation']}">{r['Data Truncation']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Date/Timestamp Mismatch'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Date/Timestamp Mismatch']}">{r['Date/Timestamp Mismatch']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['Numeric Data Mismatch'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['Numeric Data Mismatch']}">{r['Numeric Data Mismatch']:,}</td>
            <td class="px-2 py-3 text-center text-xs font-semibold border-l border-slate-200/50 dark:border-slate-700/50 {"text-slate-500 dark:text-slate-400 font-normal" if r['String Data Mismatch'] == 0 else "text-slate-700 dark:text-slate-300"}" data-val="{r['String Data Mismatch']}">{r['String Data Mismatch']:,}</td>
            <td class="px-4 py-3 text-right border-l border-slate-200 dark:border-slate-700 matrix-sticky-total glass shadow-[-2px_0_5px_-2px_rgba(0,0,0,0.1)]" data-val="{r['Total']}">{severity_badge}</td>
            <td class="px-3 py-3 text-center text-[11px] font-black text-indigo-600 dark:text-indigo-400 border-l border-slate-200/50 dark:border-slate-700/50 matrix-sticky-pct glass shadow-[-2px_0_5px_-2px_rgba(0,0,0,0.1)]" data-val="{round(r['Total']/total_diffs*100,1) if total_diffs > 0 else 0}">{round(r['Total']/total_diffs*100,1) if total_diffs > 0 else 0}%</td>
        </tr>
        <tr id="{safe_id}" class="hidden accordion-content bg-white/30 dark:bg-[#161b22]/30 transition-all duration-300 overflow-hidden">
            <td colspan="18" class="px-8 py-6 border-b-2 border-slate-100 dark:border-slate-800/80 shadow-inner">
                <div class="max-w-5xl">
                    <h3 class="text-sm font-bold text-slate-500 dark:text-slate-400 mb-4 uppercase tracking-wide flex items-center gap-2">
                        Sample Data Explorer <span class="text-indigo-500">•</span> {r['Name']}
                    </h3>
                    {samples_html}
                </div>
            </td>
        </tr>"""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>TOSCA Enterprise Integrity</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {{
                darkMode: 'class',
                theme: {{ 
                    extend: {{
                        fontFamily: {{
                            sans: ['Inter', 'system-ui', 'sans-serif'],
                        }},
                        colors: {{
                            indigo: {{ 50: '#eef2ff', 100: '#e0e7ff', 500: '#6366f1', 600: '#4f46e5', 900: '#312e81' }},
                            slate: {{ 50: '#f8fafc', 800: '#1e293b', 900: '#0d1117', 950: '#0d1117' }}
                        }},
                        animation: {{
                            'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                        }}
                    }} 
                }}
            }}
        </script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            :root {{
                --surface: 255, 255, 255;
                --surface-dark: 22, 27, 34;
                --accent: 99, 102, 241;
            }}
            ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
            ::-webkit-scrollbar-track {{ background: transparent; }}
            ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 4px; }}
            .dark ::-webkit-scrollbar-thumb {{ background: rgba(99, 102, 241, 0.5); border-radius: 4px; }}
            body {{ 
                background-color: #f8fafc; 
                font-family: 'Inter', sans-serif;
            }}
            .dark body {{ background-color: #0d1117; color: #e6edf3; }}
            
            #sidebar {{
                transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
                width: 16rem;
                overflow: hidden;
            }}
            #sidebar.collapsed {{
                width: 4.5rem;
            }}
            #sidebar .sidebar-label {{
                transition: opacity 0.25s, max-width 0.25s;
                opacity: 1;
                max-width: 200px;
                overflow: hidden;
                white-space: nowrap;
            }}
            #sidebar.collapsed .sidebar-label {{
                opacity: 0;
                max-width: 0;
            }}
            #sidebar.collapsed nav a {{
                justify-content: center;
                padding-left: 0;
                padding-right: 0;
            }}
            #sidebar.collapsed nav a svg {{
                margin: 0 auto;
            }}
            #sidebar-toggle-btn {{
                transition: all 0.3s;
            }}
            
            .glass {{
                background: rgba(var(--surface), 0.7);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(var(--surface), 0.5);
            }}
            .dark .glass {{
                background: rgba(var(--surface-dark), 0.75);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(48, 54, 61, 0.8);
            }}

            .nav-active {{
                background: rgba(var(--accent), 0.1) !important;
                color: rgb(var(--accent)) !important;
                font-weight: 700 !important;
                border-right: 3px solid rgb(var(--accent));
            }}

            .kpi-card {{
                position: relative;
                overflow: hidden;
            }}
            .kpi-card::after {{
                content: '';
                position: absolute;
                inset: 0;
                background: linear-gradient(135deg, rgba(var(--accent), 0.05) 0%, transparent 60%);
                opacity: 0;
                transition: opacity 0.3s;
            }}
            .kpi-card:hover::after {{
                opacity: 1;
            }}

            @keyframes slideDown {{
                from {{ max-height: 0; opacity: 0; }}
                to {{ max-height: 2000px; opacity: 1; }}
            }}
            .expanded {{
                display: table-row !important;
                animation: slideDown 0.4s ease-out forwards;
            }}

            /* v3.0 Staggered entrance */
            @keyframes fadeSlideUp {{
                from {{ opacity: 0; transform: translateY(24px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .stagger-card {{
                opacity: 0;
                animation: fadeSlideUp 0.5s ease-out forwards;
            }}
            .stagger-card:nth-child(1) {{ animation-delay: 0s; }}
            .stagger-card:nth-child(2) {{ animation-delay: 0.08s; }}
            .stagger-card:nth-child(3) {{ animation-delay: 0.16s; }}
            .stagger-card:nth-child(4) {{ animation-delay: 0.24s; }}
            .stagger-card:nth-child(5) {{ animation-delay: 0.32s; }}
            .stagger-card:nth-child(6) {{ animation-delay: 0.40s; }}
            .stagger-card:nth-child(7) {{ animation-delay: 0.48s; }}
            .stagger-card:nth-child(8) {{ animation-delay: 0.56s; }}

            /* v3.0 Toast */
            @keyframes toastIn {{
                from {{ opacity: 0; transform: translateY(20px) scale(0.95); }}
                to {{ opacity: 1; transform: translateY(0) scale(1); }}
            }}
            @keyframes toastOut {{
                from {{ opacity: 1; transform: translateY(0) scale(1); }}
                to {{ opacity: 0; transform: translateY(-10px) scale(0.95); }}
            }}
            .toast-enter {{ animation: toastIn 0.35s ease-out forwards; }}
            .toast-exit {{ animation: toastOut 0.3s ease-in forwards; }}

            /* v3.0 Tab system */
            .tab-btn {{
                position: relative;
                transition: all 0.2s;
                border: 1px solid rgba(226, 232, 240, 0.9);
                background: rgba(248, 250, 252, 0.85);
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            }}
            .dark .tab-btn {{
                border-color: rgba(48, 54, 61, 0.95);
                background: rgba(22, 27, 34, 0.9);
                color: #cdd9e5;
            }}
            .tab-btn.active {{
                color: #4f46e5;
                font-weight: 800;
                border-color: rgba(var(--accent), 0.45);
                background: rgba(var(--accent), 0.1);
                box-shadow: 0 8px 24px rgba(var(--accent), 0.12);
            }}
            .dark .tab-btn.active {{
                color: #c7d2fe;
            }}
            .tab-btn.active::after {{
                content: '';
                position: absolute;
                bottom: -7px;
                left: 16px;
                right: 16px;
                height: 2px;
                background: rgb(var(--accent));
                border-radius: 2px;
            }}
            .tab-panel {{ display: none; }}
            .tab-panel.active {{ display: block; }}
            .orphan-card-active {{
                border-color: rgb(99, 102, 241) !important;
                background-color: rgba(99, 102, 241, 0.05) !important;
            }}
            .dark .orphan-card-active {{
                border-color: rgb(129, 140, 248) !important;
                background-color: rgba(129, 140, 248, 0.08) !important;
            }}

            /* v3.0 Severity filter */
            .sev-filter-btn {{
                transition: all 0.2s;
                cursor: pointer;
            }}
            .sev-filter-btn.active {{
                transform: scale(1.05);
                outline: 2px solid currentColor;
                outline-offset: 1px;
            }}

            /* v3.0 Grade badge pulse */
            @keyframes gradePulse {{
                0%, 100% {{ box-shadow: 0 0 0 0 {grade_color_border}; }}
                50% {{ box-shadow: 0 0 0 6px transparent; }}
            }}
            .grade-badge {{
                animation: gradePulse 2.5s ease-in-out infinite;
            }}

            /* Info tooltip */
            .info-tooltip-wrapper:hover .info-tooltip {{
                opacity: 1;
            }}

            /* v4.0 Animated Gradient Mesh Background */
            @keyframes gradientMesh {{
                0%, 100% {{ background-position: 0% 50%; }}
                50% {{ background-position: 100% 50%; }}
            }}
            #scroll-container {{
                position: relative;
            }}
            #scroll-container::before {{
                content: '';
                position: fixed;
                inset: 0;
                background: linear-gradient(-45deg, rgba(99,102,241,0.04), rgba(139,92,246,0.03), rgba(148,163,184,0.02), rgba(99,102,241,0.04));
                background-size: 400% 400%;
                animation: gradientMesh 20s ease infinite;
                pointer-events: none;
                z-index: 0;
            }}
            .dark #scroll-container::before {{
                background: linear-gradient(-45deg, rgba(99,102,241,0.08), rgba(139,92,246,0.06), rgba(30,41,59,0.04), rgba(99,102,241,0.08));
            }}

            /* v4.0 Elevated Glassmorphism */
            .glass-card {{
                background: rgba(255,255,255,0.75);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255,255,255,0.25);
                box-shadow: 0 8px 32px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.2);
            }}
            .dark .glass-card {{
                background: rgba(22,27,34,0.8);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255,255,255,0.06);
                box-shadow: 0 8px 32px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.04);
            }}
            .glass {{
                background: rgba(var(--surface), 0.75);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(var(--surface), 0.5);
                box-shadow: 0 4px 16px rgba(0,0,0,0.03);
            }}
            .dark .glass {{
                background: rgba(var(--surface-dark), 0.8);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(48, 54, 61, 0.8);
                box-shadow: 0 4px 16px rgba(0,0,0,0.15);
            }}

            /* v4.0 Sparkline */
            .sparkline-svg {{
                width: 100%;
                height: 32px;
                display: block;
                margin-top: 12px;
                opacity: 0.5;
            }}
            .sparkline-line {{ stroke: rgba(99,102,241,0.3); }}
            .sparkline-fill {{ opacity: 0.08; }}
            .sparkline-stop1 {{ stop-color: rgba(99,102,241,0.15); }}
            .sparkline-stop2 {{ stop-color: rgba(99,102,241,0); }}
            .dark .sparkline-line {{ stroke: rgba(99,102,241,0.4); }}
            .dark .sparkline-fill {{ opacity: 0.12; }}
            .dark .sparkline-stop1 {{ stop-color: rgba(99,102,241,0.2); }}
            .dark .sparkline-stop2 {{ stop-color: rgba(99,102,241,0); }}

            /* v4.0 Character-level Diff Highlighting */
            .diff-del {{ background: rgba(239,68,68,0.15); color: #dc2626; text-decoration: line-through; border-radius: 2px; padding: 0 2px; }}
            .diff-add {{ background: rgba(34,197,94,0.15); color: #16a34a; border-radius: 2px; padding: 0 2px; }}
            .dark .diff-del {{ background: rgba(239,68,68,0.2); color: #fca5a5; }}
            .dark .diff-add {{ background: rgba(34,197,94,0.2); color: #86efac; }}

            /* v4.0 SQL Syntax Highlighting */
            .sql-keyword {{ color: #6366f1; font-weight: 700; }}
            .sql-clause {{ color: #8b5cf6; font-weight: 600; }}
            .sql-operator {{ color: #0ea5e9; }}
            .sql-function {{ color: #d97706; font-weight: 600; }}
            .sql-string {{ color: #16a34a; }}
            .sql-number {{ color: #f97316; }}
            .sql-comment {{ color: #94a3b8; font-style: italic; }}
            .dark .sql-keyword {{ color: #a5b4fc; }}
            .dark .sql-clause {{ color: #c4b5fd; }}
            .dark .sql-operator {{ color: #7dd3fc; }}
            .dark .sql-function {{ color: #fbbf24; }}
            .dark .sql-string {{ color: #86efac; }}
            .dark .sql-number {{ color: #fdba74; }}
            .dark .sql-comment {{ color: #64748b; }}

            /* v4.0 Scroll Snap */
            .snap-container {{
                scroll-snap-type: y proximity;
                scroll-padding-top: 1rem;
            }}
            .snap-section {{
                scroll-snap-align: start;
            }}

            /* v4.0 Sidebar Collapsed Tooltips */
            #sidebar.collapsed nav a {{
                position: relative;
            }}
            #sidebar.collapsed nav a:hover::after {{
                content: attr(title);
                position: absolute;
                left: calc(100% + 8px);
                top: 50%;
                transform: translateY(-50%);
                padding: 6px 12px;
                background: #0f172a;
                color: #e2e8f0;
                font-size: 11px;
                font-weight: 700;
                border-radius: 8px;
                white-space: nowrap;
                z-index: 999;
                pointer-events: none;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                border: 1px solid rgba(99,102,241,0.2);
            }}
            .dark #sidebar.collapsed nav a:hover::after {{
                background: #1e293b;
                border-color: rgba(99,102,241,0.3);
            }}

            /* v4.0 Gradient Active Nav Pill */
            .nav-active {{
                background: linear-gradient(135deg, rgba(var(--accent), 0.12), rgba(139, 92, 246, 0.08)) !important;
                color: rgb(var(--accent)) !important;
                font-weight: 700 !important;
                border-right: none;
                box-shadow: 0 2px 8px rgba(var(--accent), 0.1);
            }}

            /* v4.0 Frozen Matrix Columns */
            .matrix-sticky-total {{
                position: sticky;
                right: 70px;
                z-index: 10;
            }}
            .matrix-sticky-pct {{
                position: sticky;
                right: 0;
                z-index: 10;
            }}
            .matrix-sticky-total, .matrix-sticky-pct {{
                background: inherit;
            }}

            /* v4.0 Gradient Header */
            .gradient-header {{
                background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 50%, #f8fafc 100%);
            }}
            .dark .gradient-header {{
                background: linear-gradient(135deg, #161b22 0%, #1e1b4b 30%, #0d1117 100%);
            }}

            /* v4.0 Section Divider */
            .sidebar-section-label {{
                font-size: 9px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                color: #94a3b8;
                padding: 12px 16px 4px 16px;
            }}

            /* v4.0 Print Styles */
            @media print {{
                body {{
                    display: block !important;
                    height: auto !important;
                    overflow: visible !important;
                }}
                #sidebar, #scrollTopBtn, #sidebar-toggle-btn, #themeToggle,
                .sev-filter-btn, #mismatchTypeFilter, #activeFiltersBadge,
                #matrixSearch, #copyBtn, .tab-btn, #orphanSearch,
                #orphanPagination, .print-hide {{
                    display: none !important;
                }}
                main {{
                    display: block !important;
                    height: auto !important;
                    overflow: visible !important;
                }}
                #scroll-container {{
                    overflow: visible !important;
                    height: auto !important;
                    max-height: none !important;
                }}
                #scroll-container::before {{
                    display: none !important;
                }}
                .accordion-content {{
                    display: table-row !important;
                }}
                header {{
                    position: relative !important;
                }}
                #charts, #matrix, #test-queries {{
                    page-break-before: always;
                }}
                .tab-panel {{
                    display: block !important;
                }}
                .kpi-card::after {{ display: none; }}
                .stagger-card {{ opacity: 1 !important; animation: none !important; }}
                .grade-badge {{ animation: none !important; }}
                .sparkline-svg {{ display: none !important; }}
                * {{
                    color-adjust: exact !important;
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                }}
                .dark body {{ background: white !important; color: #0f172a !important; }}
            }}
        </style>

    </head>
    <body class="font-sans text-slate-900 dark:text-slate-100 transition-colors duration-200 antialiased flex h-screen overflow-hidden">
        
        <!-- Sidebar -->
        <aside id="sidebar" class="bg-white dark:bg-[#161b22] border-r border-slate-200 dark:border-slate-800 flex flex-col justify-between shrink-0 z-40">
            <div>
                <!-- Logo Row -->
                <div class="h-20 flex items-center px-5 border-b border-slate-100 dark:border-slate-800/50">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 shrink-0">
                            <span class="text-white font-black text-xl leading-none">T</span>
                        </div>
                        <span class="sidebar-label font-black tracking-tight text-lg dark:text-white">TOSCA DI</span>
                    </div>
                </div>
                <!-- Sidebar Toggle -->
                <div class="flex items-center justify-end px-3 pt-3 pb-1">
                    <button onclick="toggleSidebar()" id="sidebar-toggle-btn"
                        class="p-1.5 rounded-lg text-slate-400 hover:text-indigo-500 dark:hover:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                        title="Toggle sidebar">
                        <svg id="sidebar-toggle-icon" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 19l-7-7 7-7"/>
                        </svg>
                    </button>
                </div>
                <!-- Nav Links -->
                <nav class="px-3 py-2 space-y-0.5">
                    <div class="sidebar-section-label sidebar-label">Dashboard</div>
                    <a href="#kpi-section" id="nav-kpi" title="Overview" class="flex items-center gap-3 px-4 py-3 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-xl font-medium text-sm transition-all nav-active">
                        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
                        <span class="sidebar-label">Overview</span>
                    </a>
                    <a href="#charts" id="nav-charts" title="Analytics" class="flex items-center gap-3 px-4 py-3 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-xl font-medium text-sm transition-all">
                        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                        <span class="sidebar-label">Analytics</span>
                    </a>
                    <div class="sidebar-section-label sidebar-label" style="margin-top:12px">Data</div>
                    <a href="#matrix" id="nav-matrix" title="Integrity Matrix" class="flex items-center gap-3 px-4 py-3 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-xl font-medium text-sm transition-all">
                        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                        <span class="sidebar-label">Integrity Matrix</span>
                    </a>
                    <a href="#test-queries" id="nav-queries" title="Test Queries" class="flex items-center gap-3 px-4 py-3 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-xl font-medium text-sm transition-all">
                        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9h8M8 13h6m-9 8h14a2 2 0 002-2V7a2 2 0 00-.586-1.414l-3-3A2 2 0 0017 2H5a2 2 0 00-2 2v15a2 2 0 002 2z"></path></svg>
                        <span class="sidebar-label">Test Queries</span>
                    </a>
                </nav>
            </div>
            <!-- User Profile -->
            <div class="px-4 py-5 border-t border-slate-100 dark:border-slate-800/50">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-500 dark:text-slate-400 font-bold border border-slate-200 dark:border-slate-700 shadow-sm shrink-0">
                        QA
                    </div>
                    <div class="sidebar-label">
                        <p class="text-xs font-bold dark:text-slate-300">System Admin</p>
                        <p class="text-[10px] text-slate-500 font-medium">View Only</p>
                    </div>
                </div>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="flex-1 flex flex-col h-screen overflow-hidden relative">
            
            <!-- Top Header -->
            <header class="gradient-header backdrop-blur-md border-b border-slate-200 dark:border-slate-800 z-30 shrink-0 shadow-sm">
                <div class="h-20 flex items-center justify-between px-8">
                    <div class="flex items-center gap-4">
                        <div>
                            <h1 class="text-xl font-black tracking-tight dark:text-white flex items-center gap-3">
                                Dashboard Overview
                                <span class="grade-badge text-[11px] px-2.5 py-0.5 rounded-full font-black uppercase tracking-wider border" style="background:{grade_color_bg}; color:{grade_color_text}; border-color:{grade_color_border};">Grade {grade}</span>
                            </h1>
                            <p class="text-[11px] text-slate-500 dark:text-slate-400 uppercase tracking-wide font-bold mt-0.5 flex items-center gap-1.5">
                                <span>{os.path.basename(db_path)[:40]}{'...' if len(os.path.basename(db_path)) > 40 else ''}</span>
                                <span class="info-tooltip-wrapper relative inline-flex items-center">
                                    <svg class="w-3 h-3 text-slate-400 dark:text-slate-600 hover:text-indigo-500 dark:hover:text-indigo-400 cursor-default transition-colors shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>
                                    <span class="info-tooltip absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-lg text-[11px] font-mono normal-case tracking-normal whitespace-nowrap pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">{os.path.basename(db_path)}</span>
                                </span>
                            </p>
                        </div>
                    </div>
                    
                    <div class="flex items-center gap-4">
                        <div class="text-right hidden sm:block">
                            <span class="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Execution Date</span>
                            <p class="text-xs font-black text-indigo-600 dark:text-indigo-400">{report_date}</p>
                        </div>
                        <div class="h-6 w-px bg-slate-200 dark:bg-slate-700 hidden sm:block"></div>
                        <button onclick="window.print()" class="print-hide p-2.5 bg-white dark:bg-slate-800 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-all shadow-sm border border-slate-200 dark:border-slate-700 group" title="Print / Export PDF">
                            <svg class="w-5 h-5 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg>
                        </button>
                        <button id="themeToggle" class="p-2.5 bg-white dark:bg-slate-800 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-all shadow-sm border border-slate-200 dark:border-slate-700 group">
                            <svg class="w-5 h-5 hidden dark:block group-hover:rotate-12 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                            <svg class="w-5 h-5 block dark:hidden group-hover:-rotate-12 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path></svg>
                        </button>
                    </div>
                </div>
                <!-- Summary Strip -->
                <div class="h-9 bg-indigo-50/80 dark:bg-indigo-950/30 border-t border-indigo-100/50 dark:border-indigo-900/30 flex items-center justify-center gap-8 px-8 text-[10px] font-bold uppercase tracking-wider">
                    <span class="flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-indigo-500"></span><span class="text-slate-500 dark:text-slate-400">Issues:</span> <span class="text-indigo-600 dark:text-indigo-400">{total_diffs:,}</span></span>
                    <span class="text-slate-300 dark:text-slate-700">|</span>
                    <span class="flex items-center gap-1.5"><span class="text-slate-500 dark:text-slate-400">Affected:</span> <span class="text-indigo-600 dark:text-indigo-400">{affected_columns} Columns</span></span>
                    <span class="text-slate-300 dark:text-slate-700">|</span>
                    <span class="flex items-center gap-1.5"><span class="text-slate-500 dark:text-slate-400">Grade:</span> <span class="text-indigo-600 dark:text-indigo-400">{grade}</span></span>
                    <span class="text-slate-300 dark:text-slate-700">|</span>
                    <span class="flex items-center gap-1.5"><span class="text-slate-500 dark:text-slate-400">Pass Rate:</span> <span class="text-indigo-600 dark:text-indigo-400">{pass_rate}%</span></span>
                </div>
            </header>

            <!-- Scrollable Content Area -->
            <div id="scroll-container" class="flex-1 overflow-y-auto p-8 scroll-smooth relative snap-container">
                <div class="max-w-[1400px] mx-auto space-y-10 pb-12">
                    
                    <!-- Summary and KPI Cards -->
                    <section id="kpi-section" class="pt-2 snap-section">
                        <div class="mb-5">
                            <h2 class="text-lg font-black tracking-tight text-slate-900 dark:text-white">Summary and KPIs</h2>
                            <p class="text-xs text-slate-500 dark:text-slate-400 font-medium mt-1">High-level integrity metrics for the current comparison run.</p>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        <!-- Total Rows -->
                        <div class="stagger-card kpi-card glass-card p-6 rounded-3xl hover:border-indigo-500/50 dark:hover:border-indigo-400/50 hover:shadow-xl hover:shadow-indigo-500/10 transition-all duration-300 transform hover:-translate-y-1.5">
                            <div class="flex justify-between items-start mb-4">
                                <div class="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-500/10 flex items-center justify-center text-blue-600 dark:text-blue-400 shadow-inner">
                                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"></path></svg>
                                </div>
                                <span class="bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 text-[11px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wide">Dataset</span>
                            </div>
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Total Source Rows</p>
                            <h3 class="text-3xl font-black text-slate-800 dark:text-white kpi-counter" data-target="{total_rows}">0</h3>
                            {generate_sparkline_svg(total_rows, 'rows')}
                        </div>

                        <!-- Matches -->
                        <div class="stagger-card kpi-card glass-card p-6 rounded-3xl hover:border-indigo-500/50 dark:hover:border-indigo-400/50 hover:shadow-xl hover:shadow-indigo-500/10 transition-all duration-300 transform hover:-translate-y-1.5">
                            <div class="flex justify-between items-start mb-4">
                                <div class="w-12 h-12 rounded-2xl bg-green-50 dark:bg-green-500/10 flex items-center justify-center text-green-600 dark:text-green-400 shadow-inner">
                                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                </div>
                                <span class="bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400 text-[11px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wide">+{match_pct}%</span>
                            </div>
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Identical Matches</p>
                            <h3 class="text-3xl font-black text-slate-800 dark:text-white kpi-counter" data-target="{matched_count}">0</h3>
                            {generate_sparkline_svg(matched_count, 'matches')}
                        </div>

                        <!-- Differences -->
                        <div class="stagger-card kpi-card glass-card p-6 rounded-3xl hover:border-indigo-500/50 dark:hover:border-indigo-400/50 hover:shadow-xl hover:shadow-indigo-500/10 transition-all duration-300 transform hover:-translate-y-1.5">
                            <div class="flex justify-between items-start mb-4">
                                <div class="w-12 h-12 rounded-2xl bg-red-50 dark:bg-red-500/10 flex items-center justify-center text-red-600 dark:text-red-400 shadow-inner">
                                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                                </div>
                                <span class="bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400 text-[11px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wide">! {diff_pct}%</span>
                            </div>
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Rows with Diffs</p>
                            <h3 class="text-3xl font-black text-slate-800 dark:text-white kpi-counter" data-target="{diff_row_count}">0</h3>
                            {generate_sparkline_svg(diff_row_count, 'diffs')}
                        </div>

                        <!-- Pass Rate -->
                        <div class="stagger-card kpi-card glass-card p-6 rounded-3xl hover:border-indigo-500/50 dark:hover:border-indigo-400/50 hover:shadow-xl hover:shadow-indigo-500/10 transition-all duration-300 transform hover:-translate-y-1.5">
                            <div class="flex justify-between items-start mb-4">
                                <div class="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shadow-inner">
                                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                </div>
                                <span class="bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-400 text-[11px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wide">Target 100%</span>
                            </div>
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Overall Pass Rate</p>
                            <h3 class="text-3xl font-black text-slate-800 dark:text-white kpi-counter" data-target="{pass_rate}" data-suffix="%">0%</h3>
                            {generate_sparkline_svg(pass_rate, 'pass')}
                        </div>
                    </div>

                    <!-- KPI Cards Row 2 (v3.0) -->
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-6">
                        <!-- Affected Columns -->
                        <div class="stagger-card kpi-card glass-card p-6 rounded-3xl hover:border-indigo-500/50 dark:hover:border-indigo-400/50 hover:shadow-xl hover:shadow-indigo-500/10 transition-all duration-300 transform hover:-translate-y-1.5">
                            <div class="flex justify-between items-start mb-4">
                                <div class="w-12 h-12 rounded-2xl bg-purple-50 dark:bg-purple-500/10 flex items-center justify-center text-purple-600 dark:text-purple-400 shadow-inner">
                                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
                                </div>
                                <span class="bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-400 text-[11px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wide">Scope</span>
                            </div>
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Affected Columns</p>
                            <h3 class="text-3xl font-black text-slate-800 dark:text-white kpi-counter" data-target="{affected_columns}">0</h3>
                            {generate_sparkline_svg(affected_columns, 'cols')}
                        </div>

                        <!-- Critical Fields -->
                        <div class="stagger-card kpi-card glass-card p-6 rounded-3xl hover:border-indigo-500/50 dark:hover:border-indigo-400/50 hover:shadow-xl hover:shadow-indigo-500/10 transition-all duration-300 transform hover:-translate-y-1.5">
                            <div class="flex justify-between items-start mb-4">
                                <div class="w-12 h-12 rounded-2xl bg-rose-50 dark:bg-rose-500/10 flex items-center justify-center text-rose-600 dark:text-rose-400 shadow-inner">
                                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                                </div>
                                <span class="bg-rose-100 dark:bg-rose-500/20 text-rose-700 dark:text-rose-400 text-[11px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wide">Alert</span>
                            </div>
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Critical Fields</p>
                            <h3 class="text-3xl font-black text-slate-800 dark:text-white kpi-counter" data-target="{critical_fields}">0</h3>
                            {generate_sparkline_svg(critical_fields, 'critical')}
                        </div>

                        <!-- NULL Rate -->
                        <div class="stagger-card kpi-card glass-card p-6 rounded-3xl hover:border-indigo-500/50 dark:hover:border-indigo-400/50 hover:shadow-xl hover:shadow-indigo-500/10 transition-all duration-300 transform hover:-translate-y-1.5">
                            <div class="flex justify-between items-start mb-4">
                                <div class="w-12 h-12 rounded-2xl bg-amber-50 dark:bg-amber-500/10 flex items-center justify-center text-amber-600 dark:text-amber-400 shadow-inner">
                                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path></svg>
                                </div>
                                <span class="bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400 text-[11px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wide">Nulls</span>
                            </div>
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">NULL Issue Rate</p>
                            <h3 class="text-3xl font-black text-slate-800 dark:text-white kpi-counter" data-target="{null_rate}" data-suffix="%">0%</h3>
                            {generate_sparkline_svg(null_rate, 'null')}
                        </div>

                        <!-- Dominant Error -->
                        <div class="stagger-card kpi-card glass-card p-6 rounded-3xl hover:border-indigo-500/50 dark:hover:border-indigo-400/50 hover:shadow-xl hover:shadow-indigo-500/10 transition-all duration-300 transform hover:-translate-y-1.5">
                            <div class="flex justify-between items-start mb-4">
                                <div class="w-12 h-12 rounded-2xl bg-cyan-50 dark:bg-cyan-500/10 flex items-center justify-center text-cyan-600 dark:text-cyan-400 shadow-inner">
                                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                                </div>
                                <span class="bg-cyan-100 dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-400 text-[11px] font-black px-2.5 py-1 rounded-lg uppercase tracking-wide">Primary</span>
                            </div>
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">Dominant Error</p>
                            <h3 class="text-lg font-black text-slate-800 dark:text-white truncate" title="{dominant_error}">{dominant_error_short}</h3>
                            {generate_sparkline_svg(dominant_error, 'dominant')}
                        </div>
                    </div>

                    </section>

                    <!-- Analytics Section with Tabs (v3.0) -->
                    <div id="charts" class="bg-white dark:bg-[#161b22] rounded-[2rem] border border-slate-200 dark:border-slate-800 hover:border-indigo-500/50 dark:hover:border-indigo-400/50 shadow-sm transition-all duration-300 overflow-hidden snap-section">
                        <!-- Tab Header -->
                        <div class="px-8 pt-6 pb-5 flex items-center gap-3 border-b border-slate-100 dark:border-slate-800/50">
                            <button onclick="switchTab('tab-overview')" class="tab-btn active px-5 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 rounded-xl" data-tab="tab-overview">
                                <span class="flex items-center gap-2">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                                    Overview Charts
                                </span>
                            </button>
                            <button onclick="switchTab('tab-distribution')" class="tab-btn px-5 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 rounded-xl" data-tab="tab-distribution">
                                <span class="flex items-center gap-2">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"></path></svg>
                                    Error Distribution
                                </span>
                            </button>
                            <button onclick="switchTab('tab-orphans')" class="tab-btn px-5 py-3 text-xs font-bold text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 rounded-xl" data-tab="tab-orphans">
                                <span class="flex items-center gap-2">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                                    Orphaned Records
                                </span>
                            </button>
                        </div>

                        <!-- Tab 1: Overview Charts -->
                        <div id="tab-overview" class="tab-panel active p-8">
                            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                                <!-- Health Doughnut Widget -->
                                <div class="bg-slate-50/50 dark:bg-slate-800/35 rounded-2xl p-6 flex flex-col items-center">
                                    <h3 class="text-sm font-black mb-6 tracking-tight dark:text-white w-full flex items-center gap-2">
                                        <svg class="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                                        Integrity Health Score
                                    </h3>
                                    <div class="relative w-64 h-64 mb-6">
                                        <canvas id="healthChart"></canvas>
                                        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                            <span class="text-4xl font-black text-slate-800 dark:text-white">{match_pct}%</span>
                                            <span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Matched</span>
                                        </div>
                                    </div>
                                    <div class="w-full space-y-4 px-2">
                                        <div class="flex items-center justify-between group">
                                            <span class="text-xs font-bold text-slate-500 dark:text-slate-400 flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-green-500 group-hover:scale-125 transition-transform"></span>Matched
                                            </span>
                                            <span class="text-xs font-black text-slate-700 dark:text-slate-300">{match_pct}%</span>
                                        </div>
                                        <div class="flex items-center justify-between group">
                                            <span class="text-xs font-bold text-slate-500 dark:text-slate-400 flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-red-500 group-hover:scale-125 transition-transform"></span>Differences
                                            </span>
                                            <span class="text-xs font-black text-slate-700 dark:text-slate-300">{diff_pct}%</span>
                                        </div>
                                        <div class="flex items-center justify-between group">
                                            <span class="text-xs font-bold text-slate-500 dark:text-slate-400 flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-slate-400 group-hover:scale-125 transition-transform"></span>Missing/Other
                                            </span>
                                            <span class="text-xs font-black text-slate-700 dark:text-slate-300">{missing_pct}%</span>
                                        </div>
                                    </div>
                                </div>

                                <!-- Bar Chart -->
                                <div class="bg-slate-50/50 dark:bg-slate-800/35 rounded-2xl p-6 lg:col-span-2">
                                    <h3 class="text-sm font-black mb-6 tracking-tight dark:text-white flex items-center gap-2">
                                        <svg class="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                                        Top 5 Affected Columns
                                    </h3>
                                    <div class="h-72"><canvas id="barChart"></canvas></div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab 2: Error Type Distribution -->
                        <div id="tab-distribution" class="tab-panel p-8">
                            <div class="flex items-center justify-between mb-6">
                                <h3 class="text-sm font-black tracking-tight dark:text-white flex items-center gap-2">
                                    <svg class="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"></path></svg>
                                    Error Type Distribution by Column
                                </h3>
                                <div class="flex flex-wrap items-center gap-3 text-[10px] font-bold mt-2">
                                    <span class="flex items-center gap-1" title="Source Value is NULL"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Source Value is NULL']}"></span><span class="text-slate-500 dark:text-slate-400">Source NULL</span></span>
                                    <span class="flex items-center gap-1" title="Target Value is NULL"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Target Value is NULL']}"></span><span class="text-slate-500 dark:text-slate-400">Target NULL</span></span>
                                    <span class="flex items-center gap-1" title="Null Equivalent Mismatch"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Null Equivalent Mismatch']}"></span><span class="text-slate-500 dark:text-slate-400">Null Equivalent</span></span>
                                    <span class="flex items-center gap-1" title="Duplicate Value Mismatch"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Duplicate Value Mismatch']}"></span><span class="text-slate-500 dark:text-slate-400">Duplicate Value</span></span>
                                    <span class="flex items-center gap-1" title="Sorting Issue"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Sorting Issue']}"></span><span class="text-slate-500 dark:text-slate-400">Sorting Issue</span></span>
                                    <span class="flex items-center gap-1" title="Whitespace Mismatch"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Whitespace Mismatch']}"></span><span class="text-slate-500 dark:text-slate-400">Whitespace</span></span>
                                    <span class="flex items-center gap-1" title="Case Sensitivity Mismatch"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Case Sensitivity Mismatch']}"></span><span class="text-slate-500 dark:text-slate-400">Case Sensitivity</span></span>
                                    <span class="flex items-center gap-1" title="Type Coercion / Formatting"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Type Coercion / Formatting']}"></span><span class="text-slate-500 dark:text-slate-400">Type Coercion</span></span>
                                    <span class="flex items-center gap-1" title="Boolean Format Mismatch"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Boolean Format Mismatch']}"></span><span class="text-slate-500 dark:text-slate-400">Boolean Format</span></span>
                                    <span class="flex items-center gap-1" title="Encoding / Special Char Mismatch"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Encoding / Special Char Mismatch']}"></span><span class="text-slate-500 dark:text-slate-400">Encoding / Special Char</span></span>
                                    <span class="flex items-center gap-1" title="Precision / Rounding"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Precision / Rounding']}"></span><span class="text-slate-500 dark:text-slate-400">Precision / Rounding</span></span>
                                    <span class="flex items-center gap-1" title="Data Truncation"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Data Truncation']}"></span><span class="text-slate-500 dark:text-slate-400">Truncation</span></span>
                                    <span class="flex items-center gap-1" title="Date/Timestamp Mismatch"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Date/Timestamp Mismatch']}"></span><span class="text-slate-500 dark:text-slate-400">Date/Timestamp</span></span>
                                    <span class="flex items-center gap-1" title="Numeric Data Mismatch"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['Numeric Data Mismatch']}"></span><span class="text-slate-500 dark:text-slate-400">Numeric</span></span>
                                    <span class="flex items-center gap-1" title="String Data Mismatch"><span class="w-2 h-2 rounded-sm" style="background:{COLOR_MAP['String Data Mismatch']}"></span><span class="text-slate-500 dark:text-slate-400">String</span></span>
                                </div>
                            </div>
                            <div style="height: {max(320, len(sorted_matrix) * 40)}px"><canvas id="errDistChart"></canvas></div>
                        </div>

                        <!-- Tab 3: Orphaned Records -->
                        <div id="tab-orphans" class="tab-panel p-8">
                            <!-- Summary Cards -->
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                                <div onclick="switchOrphanTable('src_orphans')" class="cursor-pointer group bg-slate-50/50 dark:bg-slate-800/35 hover:bg-indigo-500/5 dark:hover:bg-indigo-500/10 rounded-2xl p-5 border border-slate-200 dark:border-slate-800 hover:border-indigo-500/30 transition-all duration-300 relative overflow-hidden">
                                    <div class="flex items-center justify-between mb-2">
                                        <span class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Source Orphans</span>
                                        <span class="w-2.5 h-2.5 rounded-full bg-amber-500 group-hover:scale-125 transition-transform duration-300"></span>
                                    </div>
                                    <h4 class="text-2xl font-black text-slate-800 dark:text-white mb-1">{src_not_found:,}</h4>
                                    <p class="text-[10px] text-slate-400 dark:text-slate-500 font-semibold leading-tight">Rows in target not found in source</p>
                                </div>
                                <div onclick="switchOrphanTable('tgt_orphans')" class="cursor-pointer group bg-slate-50/50 dark:bg-slate-800/35 hover:bg-indigo-500/5 dark:hover:bg-indigo-500/10 rounded-2xl p-5 border border-slate-200 dark:border-slate-800 hover:border-indigo-500/30 transition-all duration-300 relative overflow-hidden">
                                    <div class="flex items-center justify-between mb-2">
                                        <span class="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Target Orphans</span>
                                        <span class="w-2.5 h-2.5 rounded-full bg-orange-500 group-hover:scale-125 transition-transform duration-300"></span>
                                    </div>
                                    <h4 class="text-2xl font-black text-slate-800 dark:text-white mb-1">{tgt_not_found:,}</h4>
                                    <p class="text-[10px] text-slate-400 dark:text-slate-500 font-semibold leading-tight">Rows in source not found in target</p>
                                </div>
                            </div>

                            <!-- Table Container -->
                            <div class="bg-slate-50/30 dark:bg-slate-900/20 border border-slate-200 dark:border-slate-800 rounded-2xl p-6">
                                <!-- Header & Search -->
                                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                                    <div>
                                        <h3 id="orphanTableTitle" class="text-sm font-black tracking-tight dark:text-white mb-1">Source Orphans</h3>
                                        <p id="orphanTableDesc" class="text-[11px] text-slate-500 dark:text-slate-400">Showing records that are present in the target but missing in the source database.</p>
                                    </div>
                                    <div class="flex items-center gap-3">
                                        <!-- Search input -->
                                        <div class="relative w-full md:w-64">
                                            <input type="text" id="orphanSearch" placeholder="Search rows..." class="w-full pl-9 pr-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700/60 rounded-xl text-xs font-bold focus:outline-none focus:border-indigo-500 text-slate-800 dark:text-white transition-all shadow-sm">
                                            <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 pointer-events-none">
                                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                <!-- Actual Table Area -->
                                <div class="overflow-x-auto relative rounded-xl border border-slate-200/50 dark:border-slate-800 max-h-[500px]">
                                    <table class="w-full text-left whitespace-nowrap text-xs" id="orphanDataTable">
                                        <thead class="sticky top-0 z-10 bg-slate-100 dark:bg-slate-900 text-slate-500 dark:text-slate-400 text-[10px] uppercase font-bold tracking-wider border-b border-slate-200 dark:border-slate-800">
                                            <tr id="orphanTableHeader"></tr>
                                        </thead>
                                        <tbody id="orphanTableBody"></tbody>
                                    </table>
                                </div>

                                <!-- Pagination and empty state -->
                                <div id="orphanTableEmpty" class="hidden flex flex-col items-center justify-center py-16 text-center">
                                    <div class="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4 text-slate-400 dark:text-slate-600">
                                        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0a2 2 0 01-2 2H6a2 2 0 01-2-2m16 0V9a2 2 0 00-2-2H6a2 2 0 00-2 2v2m4.586-1H12m0 0l-1.586-1.586M12 10l1.586-1.586"></path></svg>
                                    </div>
                                    <h4 class="text-sm font-black text-slate-800 dark:text-white mb-1">No Records Found</h4>
                                    <p class="text-xs text-slate-400 dark:text-slate-500">There are no matching orphaned or invalid records for the selected type.</p>
                                </div>

                                <div id="orphanPagination" class="flex items-center justify-between mt-4 text-xs font-bold text-slate-500 dark:text-slate-400">
                                    <span id="orphanPageInfo">Page 1 of 1</span>
                                    <div class="flex items-center gap-2">
                                        <button onclick="orphanPrevPage()" id="orphanPrevBtn" class="px-3.5 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700/60 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all disabled:opacity-40">Previous</button>
                                        <button onclick="orphanNextPage()" id="orphanNextBtn" class="px-3.5 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700/60 hover:bg-slate-50 dark:hover:bg-slate-800 transition-all disabled:opacity-40">Next</button>
                                    </div>
                                </div>
                            </div>
                        </div>

                    </div>

                    <!-- Matrix Table -->
                    <div id="matrix" class="bg-white dark:bg-[#161b22] rounded-[2rem] border border-slate-200 dark:border-slate-800 hover:border-indigo-500/50 dark:hover:border-indigo-400/50 shadow-sm transition-all duration-300 overflow-hidden snap-section">
                        <div class="px-8 py-7 border-b border-slate-100 dark:border-slate-800/80 flex flex-wrap gap-4 justify-between items-center bg-slate-50/30 dark:bg-slate-800/25">
                            <div>
                                <h3 class="text-lg font-black dark:text-white flex items-center gap-3">
                                    Integrity Matrix
                                    <span class="text-[11px] bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded-md font-bold uppercase tracking-wide">{len(sorted_matrix)} Fields</span>
                                </h3>
                                <p class="text-sm text-slate-600 dark:text-slate-300 font-medium mt-1">Detailed breakdown of column-level mismatches and data gaps.</p>
                            </div>
                            <div class="flex items-center gap-3">
                                <div class="relative group">
                                    <svg class="w-4 h-4 absolute left-3.5 top-3 text-slate-400 group-focus-within:text-indigo-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                                    <input type="text" id="matrixSearch" placeholder="Filter columns..." class="text-sm pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 dark:text-white outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-sm transition-all w-64 placeholder:text-slate-400 font-medium">
                                </div>
                                <button onclick="copyToClipboard()" id="copyBtn" class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 px-5 py-2.5 rounded-xl text-xs font-black hover:bg-slate-50 dark:hover:bg-slate-700 transition-all shadow-sm flex items-center gap-2 group">
                                    <svg class="w-4 h-4 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path></svg>
                                    Copy List
                                </button>
                                <button onclick="exportCSV()" class="bg-indigo-600 text-white px-5 py-2.5 rounded-xl text-xs font-black hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-500/25 flex items-center gap-2 group">
                                    <svg class="w-4 h-4 group-hover:translate-y-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                                    Export CSV
                                </button>
                            </div>
                        </div>
                        <!-- Row-Key Columns Info Strip -->
                        <div class="px-8 py-3 border-b border-slate-100 dark:border-slate-800/50 bg-indigo-50/50 dark:bg-indigo-500/5 flex items-center gap-3 flex-wrap">
                            <span class="flex items-center gap-1.5 text-[11px] font-bold text-indigo-600 dark:text-indigo-300 uppercase tracking-wide shrink-0">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path></svg>
                                Row-Key Columns:
                            </span>
                            {row_key_badges_html}
                        </div>
                        <!-- Severity Filters & Expand/Collapse (v3.0) -->
                        <div class="px-8 py-4 border-b border-slate-100 dark:border-slate-800/50 flex flex-wrap gap-3 items-center justify-between">
                            <div class="flex flex-wrap items-center gap-3">
                                <span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide mr-1">Filter:</span>
                                <button onclick="filterSeverity('all')" class="sev-filter-btn active bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-3 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-wide border border-transparent hover:border-indigo-500/30" data-severity="all">All ({len(sorted_matrix)})</button>
                                <button onclick="filterSeverity('critical')" class="sev-filter-btn bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 px-3 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-wide border border-transparent hover:border-red-500/30" data-severity="critical">
                                    <span class="inline-flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-red-500"></span>Critical ({critical_fields})</span>
                                </button>
                                <button onclick="filterSeverity('warning')" class="sev-filter-btn bg-yellow-50 dark:bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 px-3 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-wide border border-transparent hover:border-yellow-500/30" data-severity="warning">
                                    <span class="inline-flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-yellow-500"></span>Warning ({warning_fields})</span>
                                </button>
                                <button onclick="filterSeverity('info')" class="sev-filter-btn bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 px-3 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-wide border border-transparent hover:border-slate-500/30" data-severity="info">
                                    <span class="inline-flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span>Info ({info_fields})</span>
                                </button>
                                
                                <select id="mismatchTypeFilter" onchange="filterMismatchType()" class="text-[11px] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 px-3 py-1.5 rounded-lg font-bold outline-none focus:border-indigo-500 shadow-sm transition-all">
                                    <option value="all">All Mismatch Types</option>
                                    <option value="1">Source Value is NULL</option>
                                    <option value="2">Target Value is NULL</option>
                                    <option value="3">Null Equivalent Mismatch</option>
                                    <option value="4">Duplicate Value Mismatch</option>
                                    <option value="5">Sorting Issue</option>
                                    <option value="6">Whitespace Mismatch</option>
                                    <option value="7">Case Sensitivity Mismatch</option>
                                    <option value="8">Type Coercion / Formatting</option>
                                    <option value="9">Boolean Format Mismatch</option>
                                    <option value="10">Encoding / Special Char Mismatch</option>
                                    <option value="11">Precision / Rounding</option>
                                    <option value="12">Data Truncation</option>
                                    <option value="13">Date/Timestamp Mismatch</option>
                                    <option value="14">Numeric Data Mismatch</option>
                                    <option value="15">String Data Mismatch</option>
                                </select>

                                <div id="activeFiltersBadge" class="hidden flex items-center gap-2 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 px-3 py-1.5 rounded-lg text-[10px] font-bold border border-indigo-200/50 dark:border-indigo-800/40 transition-all">
                                    <span class="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse"></span>
                                    <span>Filters: <span id="activeFiltersText" class="font-black text-slate-800 dark:text-slate-200"></span></span>
                                    <button onclick="clearAllFilters()" class="hover:text-red-500 font-black ml-1.5 text-xs transition-colors" title="Clear Filters">×</button>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <button onclick="expandAllAccordions()" class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 px-3 py-1.5 rounded-lg text-[11px] font-bold hover:text-indigo-600 dark:hover:text-indigo-400 transition-all flex items-center gap-1.5">
                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path></svg>
                                    Expand All
                                </button>
                                <button onclick="collapseAllAccordions()" class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 px-3 py-1.5 rounded-lg text-[11px] font-bold hover:text-indigo-600 dark:hover:text-indigo-400 transition-all flex items-center gap-1.5">
                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25"></path></svg>
                                    Collapse All
                                </button>
                            </div>
                        </div>
                        <div class="overflow-x-auto relative scroll-smooth rounded-b-2xl" style="max-height: 800px; min-height: 280px;">
                            <table class="w-full text-left whitespace-nowrap text-xs" id="matrixTable">
                                <thead class="sticky top-0 z-20 bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 text-[10px] uppercase font-black tracking-wide border-b border-slate-200 dark:border-slate-800 shadow-sm">
                                    <tr>
                                        <th class="px-4 py-3 cursor-pointer sticky left-0 z-30 glass shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)] hover:text-indigo-600 transition-colors" onclick="sortTable(0, false)">Field ↕</th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(1, true)">
                                            Src NULL ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Source Value is NULL</strong>
                                                <span class="text-slate-300 leading-tight block">Record exists in target but is missing or null in the source system.</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(2, true)">
                                            Tgt NULL ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Target Value is NULL</strong>
                                                <span class="text-slate-300 leading-tight block">Record exists in source but is missing or null in the target system.</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(3, true)">
                                            Null Eqv ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Null Equivalent Mismatch</strong>
                                                <span class="text-slate-300 leading-tight block">One system has a real null, while the other has a null-equivalent string (e.g. 'NULL', 'None').</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(4, true)">
                                            Dupe ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Duplicate Value Mismatch</strong>
                                                <span class="text-slate-300 leading-tight block">Records are duplicated in one system but not the other.</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(5, true)">
                                            Sorting ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Sorting Issue</strong>
                                                <span class="text-slate-300 leading-tight block">Data is identical but returned in a different order.</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(6, true)">
                                            WhtSpc ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Whitespace Mismatch</strong>
                                                <span class="text-slate-300 leading-tight block">Values differ only by leading, trailing, or multiple spaces.</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(7, true)">
                                            Case ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Case Sensitivity Mismatch</strong>
                                                <span class="text-slate-300 leading-tight block">Values differ only by uppercase/lowercase letters.</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(8, true)">
                                            Coerce ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Type Coercion / Formatting</strong>
                                                <span class="text-slate-300 leading-tight block">Data types differ (e.g., integer vs float) or formatting varies (e.g., 1,000 vs 1000).</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(9, true)">
                                            Bool ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Boolean Format Mismatch</strong>
                                                <span class="text-slate-300 leading-tight block">Boolean values represented differently (e.g., True/False vs 1/0 or Y/N).</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(10, true)">
                                            Enc ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Encoding / Special Char Mismatch</strong>
                                                <span class="text-slate-300 leading-tight block">Mismatches caused by character encoding issues or special characters (e.g., UTF-8 vs ASCII).</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(11, true)">
                                            Round ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Precision / Rounding</strong>
                                                <span class="text-slate-300 leading-tight block">Numeric values differ slightly due to decimal precision or rounding rules.</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(12, true)">
                                            Trunc ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Data Truncation</strong>
                                                <span class="text-slate-300 leading-tight block">A string value in one system is cut off due to column length limits.</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(13, true)">
                                            Date ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Date/Timestamp Mismatch</strong>
                                                <span class="text-slate-300 leading-tight block">Dates or timestamps format differently (e.g., YYYY-MM-DD vs MM/DD/YYYY).</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(14, true)">
                                            Numeric ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Numeric Data Mismatch</strong>
                                                <span class="text-slate-300 leading-tight block">Completely different numeric values found for the same row key.</span>
                                            </span>
                                        </th>
                                        <th class="px-2 py-3 text-center cursor-pointer border-l border-slate-200/50 dark:border-slate-700/50 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative" onclick="sortTable(15, true)">
                                            String ↕
                                            <span class="info-tooltip absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">String Data Mismatch</strong>
                                                <span class="text-slate-300 leading-tight block">Completely different text strings found for the same row key.</span>
                                            </span>
                                        </th>
                                        <th class="px-4 py-3 text-right cursor-pointer border-l border-slate-200 dark:border-slate-700 hover:text-indigo-600 transition-colors info-tooltip-wrapper relative matrix-sticky-total glass shadow-[-2px_0_5px_-2px_rgba(0,0,0,0.1)]" onclick="sortTable(16, true)">
                                            Total ↕
                                            <span class="info-tooltip absolute top-full right-0 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Total Issues</strong>
                                                <span class="text-slate-300 leading-tight block">The aggregate count of all error types found for this column.</span>
                                            </span>
                                        </th>
                                        <th class="px-3 py-3 text-center border-l border-slate-200/50 dark:border-slate-700/50 text-indigo-500 dark:text-indigo-400 info-tooltip-wrapper relative matrix-sticky-pct glass shadow-[-2px_0_5px_-2px_rgba(0,0,0,0.1)]">
                                            % Total
                                            <span class="info-tooltip absolute top-full right-0 mt-2 px-3 py-2.5 rounded-lg text-[11px] font-mono normal-case tracking-normal w-56 whitespace-normal text-left pointer-events-none z-50 opacity-0 transition-opacity duration-200 bg-slate-900 dark:bg-slate-700 text-slate-100 border border-slate-700 dark:border-slate-600 shadow-xl">
                                                <strong class="block text-indigo-400 mb-1">Percentage of Total</strong>
                                                <span class="text-slate-300 leading-tight block">The percentage of overall dataset differences attributed to this specific column.</span>
                                            </span>
                                        </th>
                                    </tr>
                                </thead>
                                <tbody id="matrixBody">{table_body}</tbody>
                                <tfoot class="sticky bottom-0 z-20 bg-slate-100/95 dark:bg-slate-800/95 backdrop-blur border-t-2 border-slate-300 dark:border-slate-700 text-[10px] font-black uppercase tracking-wide text-slate-500 dark:text-slate-400">
                                    <tr>
                                        <td class="px-4 py-3 sticky left-0 z-30 glass shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)] text-slate-700 dark:text-slate-300">Totals</td>
                                        {col_totals_html}
                                        <td class="px-4 py-3 text-right border-l border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 matrix-sticky-total glass shadow-[-2px_0_5px_-2px_rgba(0,0,0,0.1)]">{total_diffs:,}</td>
                                        <td class="px-3 py-3 text-center text-indigo-500 dark:text-indigo-400 matrix-sticky-pct glass shadow-[-2px_0_5px_-2px_rgba(0,0,0,0.1)]">100%</td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    </div>

                    <!-- Test Queries Section -->
                    <div id="test-queries" class="bg-white dark:bg-[#161b22] rounded-[2rem] border border-slate-200 dark:border-slate-800 hover:border-indigo-500/50 dark:hover:border-indigo-400/50 shadow-sm transition-all duration-300 overflow-hidden snap-section">
                        <div class="px-8 py-7 border-b border-slate-100 dark:border-slate-800/80 bg-slate-50/30 dark:bg-slate-800/25">
                            <h3 class="text-lg font-black dark:text-white flex items-center gap-3">
                                Test Queries
                                <span class="text-[11px] bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 px-2 py-0.5 rounded-md font-bold uppercase tracking-wide">Source vs Target</span>
                            </h3>
                            <p class="text-sm text-slate-600 dark:text-slate-300 font-medium mt-1">Connection details and SQL used for the comparison run.</p>
                        </div>
                        <div class="p-8">
                            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                <div class="bg-slate-50/50 dark:bg-slate-800/35 rounded-2xl p-6 border border-slate-100 dark:border-slate-800">
                                    <div class="flex items-center justify-between mb-4">
                                        <h4 class="text-sm font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2">
                                            <svg class="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"></path></svg>
                                            Source Details
                                        </h4>
                                        <button onclick="copySqlToClipboard('source-sql')" class="text-slate-500 dark:text-slate-300 hover:text-indigo-500 transition-colors" title="Copy SQL">
                                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path></svg>
                                        </button>
                                    </div>
                                    <div class="mb-4 flex items-center gap-2">
                                        <span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Type:</span>
                                        <span class="text-xs font-bold text-slate-700 dark:text-slate-300 bg-slate-200 dark:bg-slate-800 px-2 py-0.5 rounded-md">{source_type}</span>
                                    </div>
                                    <div class="mb-4">
                                        <span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide block mb-1">Connection String/DSN:</span>
                                        <code class="text-[13px] leading-5 block bg-slate-50 dark:bg-slate-700 text-slate-700 dark:text-slate-100 p-3 rounded-lg border border-slate-300 dark:border-slate-600 break-all">{source_desc}</code>
                                    </div>
                                    <div>
                                        <span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide block mb-2">SQL Query:</span>
                                        <pre id="source-sql" class="text-[13px] leading-5 font-medium font-mono bg-slate-50 text-slate-800 dark:bg-slate-700 dark:text-slate-100 p-4 rounded-xl overflow-x-auto border border-slate-300 dark:border-slate-600 whitespace-pre-wrap">{highlight_sql(source_sql)}</pre>
                                    </div>
                                </div>
                                <div class="bg-slate-50/50 dark:bg-slate-800/35 rounded-2xl p-6 border border-slate-100 dark:border-slate-800">
                                    <div class="flex items-center justify-between mb-4">
                                        <h4 class="text-sm font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wide flex items-center gap-2">
                                            <svg class="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"></path></svg>
                                            Target Details
                                        </h4>
                                        <button onclick="copySqlToClipboard('target-sql')" class="text-slate-500 dark:text-slate-300 hover:text-indigo-500 transition-colors" title="Copy SQL">
                                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path></svg>
                                        </button>
                                    </div>
                                    <div class="mb-4 flex items-center gap-2">
                                        <span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Type:</span>
                                        <span class="text-xs font-bold text-slate-700 dark:text-slate-300 bg-slate-200 dark:bg-slate-800 px-2 py-0.5 rounded-md">{target_type}</span>
                                    </div>
                                    <div class="mb-4">
                                        <span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide block mb-1">Connection String/DSN:</span>
                                        <code class="text-[13px] leading-5 block bg-slate-50 dark:bg-slate-700 text-slate-700 dark:text-slate-100 p-3 rounded-lg border border-slate-300 dark:border-slate-600 break-all">{target_desc}</code>
                                    </div>
                                    <div>
                                        <span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide block mb-2">SQL Query:</span>
                                        <pre id="target-sql" class="text-[13px] leading-5 font-medium font-mono bg-slate-50 text-slate-800 dark:bg-slate-700 dark:text-slate-100 p-4 rounded-xl overflow-x-auto border border-slate-300 dark:border-slate-600 whitespace-pre-wrap">{highlight_sql(target_sql)}</pre>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>


                    <!-- Footer Branding -->
                    <footer class="pt-8 border-t border-slate-200 dark:border-slate-800 text-center pb-8 print-hide">
                        <div class="flex items-center justify-center gap-2 mb-2 text-slate-400 dark:text-slate-600">
                            <div class="w-6 h-6 rounded-md bg-slate-100 dark:bg-slate-800 flex items-center justify-center font-black text-xs">T</div>
                            <span class="text-[10px] font-extrabold uppercase tracking-widest">TOSCA DI</span>
                        </div>
                        <p class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider">
                            Generated on {report_date} • TOSCA DI Engine v4.0 • {len(sorted_matrix)} fields analyzed • {total_issues_all:,} total issues
                        </p>
                    </footer>
                </div>
            </div>

            <!-- Scroll-to-Top Button -->
            <button id="scrollTopBtn" onclick="document.getElementById('scroll-container').scrollTo({{top:0,behavior:'smooth'}})" class="fixed bottom-8 right-8 w-12 h-12 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl shadow-xl shadow-indigo-500/30 flex items-center justify-center transition-all duration-300 translate-y-24 opacity-0 z-50 group">
                <svg class="w-6 h-6 group-hover:-translate-y-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"></path></svg>
            </button>
        </main>

        <script>
            // Theme Toggle Logic
            const themeToggle = document.getElementById('themeToggle');
            const htmlClass = document.documentElement.classList;
            
            if (localStorage.theme === 'dark') {{
                htmlClass.add('dark');
            }} else {{
                htmlClass.remove('dark');
            }}

            themeToggle.addEventListener('click', () => {{
                if (htmlClass.contains('dark')) {{
                    htmlClass.remove('dark');
                    localStorage.theme = 'light';
                }} else {{
                    htmlClass.add('dark');
                    localStorage.theme = 'dark';
                }}
                updateChartColors();
            }});

            // Chart Configurations
            const getChartTextColor = () => htmlClass.contains('dark') ? '#94a3b8' : '#64748b';
            const getGridColor = () => htmlClass.contains('dark') ? 'rgba(30, 41, 59, 0.5)' : 'rgba(226, 232, 240, 0.5)';

            Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
            Chart.defaults.color = getChartTextColor();

            // Bar Chart Initialization
            const barCtx = document.getElementById('barChart').getContext('2d');
            const barGradient = barCtx.createLinearGradient(0, 0, 400, 0);
            barGradient.addColorStop(0, '#4f46e5');
            barGradient.addColorStop(1, '#818cf8');

            let barChart = new Chart(barCtx, {{
                type: 'bar',
                data: {{
                    labels: {bar_chart_labels},
                    datasets: [{{
                        label: 'Total Issues',
                        data: {bar_chart_values},
                        backgroundColor: barGradient,
                        hoverBackgroundColor: '#a5b4fc',
                        borderRadius: 8,
                        barPercentage: 0.6,
                        categoryPercentage: 0.8
                    }}]
                }},
                options: {{
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    onHover: (e, elements) => {{
                        e.native.target.style.cursor = elements && elements.length > 0 ? 'pointer' : 'default';
                    }},
                    onClick: (e, elements) => {{
                        if (elements && elements.length > 0) {{
                            const elementIndex = elements[0].index;
                            const label = barChart.data.labels[elementIndex];
                            
                            const matrixSearchInput = document.getElementById('matrixSearch');
                            if (matrixSearchInput) {{
                                matrixSearchInput.value = label;
                                matrixSearchInput.dispatchEvent(new Event('input'));
                                
                                const matrixEl = document.getElementById('matrix');
                                if (matrixEl) {{
                                    matrixEl.scrollIntoView({{ behavior: 'smooth' }});
                                }}
                                
                                setTimeout(() => {{
                                    const rows = document.querySelectorAll('.matrix-row');
                                    rows.forEach(row => {{
                                        const colName = row.querySelector('.col-name').innerText.toLowerCase();
                                        if (colName.includes(label.toLowerCase())) {{
                                            const accId = row.getAttribute('onclick').match(/'([^']+)'/)[1];
                                            const accRow = document.getElementById(accId);
                                            if (accRow.classList.contains('hidden')) {{
                                                row.click();
                                            }}
                                        }}
                                    }});
                                }}, 500);
                                showToast('Filtered Integrity Matrix for column: ' + label);
                            }}
                        }}
                    }},
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            backgroundColor: htmlClass.contains('dark') ? '#1e293b' : '#ffffff',
                            titleColor: htmlClass.contains('dark') ? '#ffffff' : '#0d1117',
                            bodyColor: htmlClass.contains('dark') ? '#cbd5e1' : '#475569',
                            borderColor: htmlClass.contains('dark') ? 'rgba(99, 102, 241, 0.2)' : '#e2e8f0',
                            borderWidth: 1,
                            padding: 12,
                            displayColors: false,
                            cornerRadius: 12,
                            titleFont: {{ weight: '800' }}
                        }}
                    }},
                    scales: {{
                        x: {{ 
                            beginAtZero: true, 
                            grid: {{ color: getGridColor(), drawBorder: false }},
                            ticks: {{ font: {{ weight: '600' }} }}
                        }},
                        y: {{ 
                            grid: {{ display: false, drawBorder: false }},
                            ticks: {{ font: {{ weight: '600' }} }}
                        }}
                    }}
                }}
            }});

            // Health Doughnut Chart
            const healthCtx = document.getElementById('healthChart').getContext('2d');
            let healthChart = new Chart(healthCtx, {{
                type: 'doughnut',
                data: {{
                    labels: ['Matched', 'Differences', 'Missing'],
                    datasets: [{{
                        data: [{match_pct}, {diff_pct}, {missing_pct}],
                        backgroundColor: ['#22c55e', '#ef4444', '#94a3b8'],
                        borderWidth: 0,
                        hoverOffset: 10,
                        cutout: '80%'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    layout: {{ padding: 20 }},
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            backgroundColor: '#1e293b',
                            titleColor: '#ffffff',
                            bodyColor: '#cbd5e1',
                            borderColor: 'rgba(99, 102, 241, 0.4)',
                            borderWidth: 1,
                            padding: 12,
                            cornerRadius: 12,
                            titleFont: {{ weight: '800' }}
                        }}
                    }}
                }}
            }});

            // Error Distribution Chart (v3.0) - lazy initialized
            let errDistChart = null;
            function initErrDistChart() {{
                const ctx = document.getElementById('errDistChart');
                if (!ctx) return;
                const isDark = htmlClass.contains('dark');
                errDistChart = new Chart(ctx.getContext('2d'), {{
                    type: 'bar',
                    data: {{
                        labels: {err_dist_labels},
                        datasets: [
                            {{ label: 'Source Value is NULL', data: {err_dist_data['Source Value is NULL']}, backgroundColor: '{COLOR_MAP["Source Value is NULL"]}', borderRadius: 2 }},
                            {{ label: 'Target Value is NULL', data: {err_dist_data['Target Value is NULL']}, backgroundColor: '{COLOR_MAP["Target Value is NULL"]}', borderRadius: 2 }},
                            {{ label: 'Null Equivalent Mismatch', data: {err_dist_data['Null Equivalent Mismatch']}, backgroundColor: '{COLOR_MAP["Null Equivalent Mismatch"]}', borderRadius: 2 }},
                            {{ label: 'Duplicate Value Mismatch', data: {err_dist_data['Duplicate Value Mismatch']}, backgroundColor: '{COLOR_MAP["Duplicate Value Mismatch"]}', borderRadius: 2 }},
                            {{ label: 'Sorting Issue', data: {err_dist_data['Sorting Issue']}, backgroundColor: '{COLOR_MAP["Sorting Issue"]}', borderRadius: 2 }},
                            {{ label: 'Whitespace Mismatch', data: {err_dist_data['Whitespace Mismatch']}, backgroundColor: '{COLOR_MAP["Whitespace Mismatch"]}', borderRadius: 2 }},
                            {{ label: 'Case Sensitivity Mismatch', data: {err_dist_data['Case Sensitivity Mismatch']}, backgroundColor: '{COLOR_MAP["Case Sensitivity Mismatch"]}', borderRadius: 2 }},
                            {{ label: 'Type Coercion / Formatting', data: {err_dist_data['Type Coercion / Formatting']}, backgroundColor: '{COLOR_MAP["Type Coercion / Formatting"]}', borderRadius: 2 }},
                            {{ label: 'Boolean Format Mismatch', data: {err_dist_data['Boolean Format Mismatch']}, backgroundColor: '{COLOR_MAP["Boolean Format Mismatch"]}', borderRadius: 2 }},
                            {{ label: 'Encoding / Special Char Mismatch', data: {err_dist_data['Encoding / Special Char Mismatch']}, backgroundColor: '{COLOR_MAP["Encoding / Special Char Mismatch"]}', borderRadius: 2 }},
                            {{ label: 'Precision / Rounding', data: {err_dist_data['Precision / Rounding']}, backgroundColor: '{COLOR_MAP["Precision / Rounding"]}', borderRadius: 2 }},
                            {{ label: 'Data Truncation', data: {err_dist_data['Data Truncation']}, backgroundColor: '{COLOR_MAP["Data Truncation"]}', borderRadius: 2 }},
                            {{ label: 'Date/Timestamp Mismatch', data: {err_dist_data['Date/Timestamp Mismatch']}, backgroundColor: '{COLOR_MAP["Date/Timestamp Mismatch"]}', borderRadius: 2 }},
                            {{ label: 'Numeric Data Mismatch', data: {err_dist_data['Numeric Data Mismatch']}, backgroundColor: '{COLOR_MAP["Numeric Data Mismatch"]}', borderRadius: 2 }},
                            {{ label: 'String Data Mismatch', data: {err_dist_data['String Data Mismatch']}, backgroundColor: '{COLOR_MAP["String Data Mismatch"]}', borderRadius: 2 }}
                        ]
                    }},
                    options: {{
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: false }},
                            tooltip: {{
                                backgroundColor: isDark ? '#1e293b' : '#ffffff',
                                titleColor: isDark ? '#ffffff' : '#0d1117',
                                bodyColor: isDark ? '#cbd5e1' : '#475569',
                                borderColor: isDark ? 'rgba(99, 102, 241, 0.2)' : '#e2e8f0',
                                borderWidth: 1,
                                padding: 12,
                                cornerRadius: 12,
                                titleFont: {{ weight: '800' }}
                            }}
                        }},
                        scales: {{
                            x: {{ stacked: true, grid: {{ color: getGridColor(), drawBorder: false }}, ticks: {{ font: {{ weight: '600' }} }} }},
                            y: {{ stacked: true, grid: {{ display: false }}, ticks: {{ font: {{ weight: '600', size: 10 }}, autoSkip: false }} }}
                        }}
                    }}
                }});
            }}

            function updateChartColors() {{
                const isDark = htmlClass.contains('dark');
                const color = getChartTextColor();
                const gridColor = getGridColor();
                
                // Tooltip theme
                const tooltipBg = isDark ? '#1e293b' : '#ffffff';
                const tooltipTitle = isDark ? '#ffffff' : '#0d1117';
                const tooltipBody = isDark ? '#cbd5e1' : '#475569';
                
                // Update Bar Chart
                barChart.options.scales.y.ticks.color = color;
                barChart.options.scales.x.ticks.color = color;
                barChart.options.scales.x.grid.color = gridColor;
                barChart.options.plugins.tooltip.backgroundColor = tooltipBg;
                barChart.options.plugins.tooltip.titleColor = tooltipTitle;
                barChart.options.plugins.tooltip.bodyColor = tooltipBody;
                barChart.update();
                
                // Update Doughnut
                healthChart.options.plugins.tooltip.backgroundColor = tooltipBg;
                healthChart.options.plugins.tooltip.titleColor = tooltipTitle;
                healthChart.options.plugins.tooltip.bodyColor = tooltipBody;
                healthChart.update();

                // Update Error Distribution Chart (v3.0)
                if (errDistChart) {{
                    errDistChart.options.scales.x.ticks.color = color;
                    errDistChart.options.scales.y.ticks.color = color;
                    errDistChart.options.scales.x.grid.color = gridColor;
                    errDistChart.options.plugins.tooltip.backgroundColor = tooltipBg;
                    errDistChart.options.plugins.tooltip.titleColor = tooltipTitle;
                    errDistChart.options.plugins.tooltip.bodyColor = tooltipBody;
                    errDistChart.update();
                }}
            }}

            // KPI Counter Animation
            function animateCounters() {{
                const counters = document.querySelectorAll('.kpi-counter');
                counters.forEach(counter => {{
                    const target = parseFloat(counter.getAttribute('data-target'));
                    const suffix = counter.getAttribute('data-suffix') || '';
                    const duration = 1500;
                    const startTime = performance.now();
                    
                    function update(currentTime) {{
                        const elapsed = currentTime - startTime;
                        const progress = Math.min(elapsed / duration, 1);
                        const easeOut = 1 - Math.pow(1 - progress, 3);
                        const current = easeOut * target;
                        
                        if (target % 1 === 0) {{
                            counter.innerText = Math.floor(current).toLocaleString() + suffix;
                        }} else {{
                            counter.innerText = current.toFixed(1) + suffix;
                        }}
                        
                        if (progress < 1) requestAnimationFrame(update);
                    }}
                    requestAnimationFrame(update);
                }});
            }}

            // Scroll Logic (Scroll-to-Top & Scroll-Spy)
            const scrollContainer = document.getElementById('scroll-container');
            const scrollTopBtn = document.getElementById('scrollTopBtn');
            const sections = ['kpi-section', 'charts', 'matrix', 'test-queries'];
            const navLinks = {{
                'kpi-section': document.getElementById('nav-kpi'),
                'charts': document.getElementById('nav-charts'),
                'test-queries': document.getElementById('nav-queries'),
                'matrix': document.getElementById('nav-matrix')
            }};

            let isAutoScrolling = false;
            let autoScrollTimer = null;

            scrollContainer.addEventListener('scroll', () => {{
                // Scroll-to-Top Visibility
                if (scrollContainer.scrollTop > 300) {{
                    scrollTopBtn.classList.remove('translate-y-24', 'opacity-0');
                    scrollTopBtn.classList.add('translate-y-0', 'opacity-100');
                }} else {{
                    scrollTopBtn.classList.add('translate-y-24', 'opacity-0');
                    scrollTopBtn.classList.remove('translate-y-0', 'opacity-100');
                }}

                if (isAutoScrolling) return;

                // Scroll-Spy Highlighting
                let currentSection = '';
                const isAtBottom = Math.abs(scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight) < 10;
                
                if (scrollContainer.scrollTop === 0) {{
                    currentSection = sections[0];
                }} else if (isAtBottom) {{
                    currentSection = sections[sections.length - 1];
                }} else {{
                    const containerRect = scrollContainer.getBoundingClientRect();
                    const threshold = containerRect.top + 100;
                    
                    sections.forEach(id => {{
                        const el = document.getElementById(id);
                        if (!el) return;
                        const rect = el.getBoundingClientRect();
                        if (rect.top <= threshold && rect.bottom > threshold) {{
                            currentSection = id;
                        }}
                    }});
                }}

                if (currentSection && navLinks[currentSection]) {{
                    Object.values(navLinks).forEach(link => link.classList.remove('nav-active'));
                    navLinks[currentSection].classList.add('nav-active');
                }}
            }});

            // Sidebar Navigation Smooth Scroll & Active State
            document.querySelectorAll('#sidebar nav a').forEach(link => {{
                link.addEventListener('click', (e) => {{
                    const targetId = link.getAttribute('href');
                    if (!targetId || !targetId.startsWith('#')) return;
                    const targetEl = document.getElementById(targetId.substring(1));
                    if (targetEl) {{
                        e.preventDefault();
                        
                        isAutoScrolling = true;
                        if (autoScrollTimer) clearTimeout(autoScrollTimer);
                        
                        const containerRect = scrollContainer.getBoundingClientRect();
                        const targetRect = targetEl.getBoundingClientRect();
                        const targetTop = targetRect.top - containerRect.top + scrollContainer.scrollTop;
                        
                        scrollContainer.scrollTo({{
                            top: targetTop - 16,
                            behavior: 'smooth'
                        }});
                        
                        // Set active class immediately
                        Object.values(navLinks).forEach(l => l.classList.remove('nav-active'));
                        link.classList.add('nav-active');
                        
                        // Update hash without jumping
                        history.pushState(null, null, targetId);
                        
                        autoScrollTimer = setTimeout(() => {{
                            isAutoScrolling = false;
                        }}, 800);
                    }}
                }});
            }});


            // Accordion Logic (Animated)
            function toggleAccordion(id) {{
                const allAccordions = document.querySelectorAll('.accordion-content');
                const clickedAcc = document.getElementById(id);
                const isCurrentlyOpen = !clickedAcc.classList.contains('hidden');

                allAccordions.forEach(acc => {{
                    if(!acc.classList.contains('hidden')) {{
                        acc.classList.add('hidden');
                        acc.classList.remove('expanded');
                        acc.previousElementSibling.querySelector('.col-name span').classList.remove('rotate-90');
                        acc.previousElementSibling.querySelector('.col-name span').innerText = '▶';
                    }}
                }});

                if(!isCurrentlyOpen) {{
                    clickedAcc.classList.remove('hidden');
                    clickedAcc.classList.add('expanded');
                    const arrow = clickedAcc.previousElementSibling.querySelector('.col-name span');
                    arrow.innerText = '▼';
                    arrow.classList.add('rotate-90');
                }}
            }}

            // v3.0: Tab Switching
            function switchTab(tabId) {{
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');
                document.querySelector(`[data-tab="${{tabId}}"]`).classList.add('active');
                // Lazy-init error distribution chart on first tab switch
                if (tabId === 'tab-distribution' && !errDistChart) {{
                    initErrDistChart();
                }}
                if (tabId === 'tab-orphans') {{
                    switchOrphanTable(currentOrphanType);
                }}
            }}

            // Orphan/Invalid Records Data
            const unmatchedSrcData = {unmatched_src_json};
            const unmatchedTgtData = {unmatched_tgt_json};
            const invalidSrcData = {invalid_src_json};
            const invalidTgtData = {invalid_tgt_json};

            let currentOrphanType = 'src_orphans';
            let orphanPage = 1;
            const orphanPageSize = 10;
            let orphanSearchText = '';

            function switchOrphanTable(type) {{
                currentOrphanType = type;
                orphanPage = 1;
                orphanSearchText = '';
                document.getElementById('orphanSearch').value = '';
                
                // Highlight active card
                const cards = document.querySelectorAll('#tab-orphans .grid > div');
                cards.forEach(c => c.classList.remove('orphan-card-active', 'border-indigo-500', 'dark:border-indigo-400'));
                
                let targetCardIndex = 0;
                let title = 'Source Orphans';
                let desc = 'Showing records that are present in the target but missing in the source database.';
                
                if (type === 'src_orphans') {{
                    targetCardIndex = 0;
                    title = 'Source Orphans';
                    desc = 'Showing records that are present in the target but missing in the source database.';
                }} else if (type === 'tgt_orphans') {{
                    targetCardIndex = 1;
                    title = 'Target Orphans';
                    desc = 'Showing records that are present in the source but missing in the target database.';
                }} else if (type === 'src_invalid') {{
                    targetCardIndex = 2;
                    title = 'Invalid Source';
                    desc = 'Showing source records that fail data validation rules.';
                }} else if (type === 'tgt_invalid') {{
                    targetCardIndex = 3;
                    title = 'Invalid Target';
                    desc = 'Showing target records that fail data validation rules.';
                }}
                
                if (cards && cards[targetCardIndex]) {{
                    cards[targetCardIndex].classList.add('orphan-card-active', 'border-indigo-500', 'dark:border-indigo-400');
                }}
                document.getElementById('orphanTableTitle').innerText = title;
                document.getElementById('orphanTableDesc').innerText = desc;
                
                renderOrphanTable();
            }}

            function renderOrphanTable() {{
                let data = null;
                if (currentOrphanType === 'src_orphans') data = unmatchedSrcData;
                else if (currentOrphanType === 'tgt_orphans') data = unmatchedTgtData;
                else if (currentOrphanType === 'src_invalid') data = invalidSrcData;
                else if (currentOrphanType === 'tgt_invalid') data = invalidTgtData;

                const columns = data ? data.columns : [];
                const rows = data ? data.rows : [];
                
                // Filter rows based on search
                let filtered = rows;
                if (orphanSearchText) {{
                    const term = orphanSearchText.toLowerCase();
                    filtered = rows.filter(r => r.some(val => val !== null && String(val).toLowerCase().includes(term)));
                }}

                // Update headers
                const headerRow = document.getElementById('orphanTableHeader');
                headerRow.innerHTML = '';
                columns.forEach(col => {{
                    const th = document.createElement('th');
                    th.className = 'px-4 py-3 text-left font-bold border-l border-slate-200/50 dark:border-slate-800';
                    th.innerText = col;
                    headerRow.appendChild(th);
                }});

                // Paginate
                const totalRows = filtered.length;
                const totalPages = Math.ceil(totalRows / orphanPageSize) || 1;
                if (orphanPage > totalPages) orphanPage = totalPages;

                const startIdx = (orphanPage - 1) * orphanPageSize;
                const endIdx = Math.min(startIdx + orphanPageSize, totalRows);
                const pageRows = filtered.slice(startIdx, endIdx);

                const body = document.getElementById('orphanTableBody');
                body.innerHTML = '';
                
                if (totalRows === 0) {{
                    document.getElementById('orphanDataTable').classList.add('hidden');
                    document.getElementById('orphanTableEmpty').classList.remove('hidden');
                    document.getElementById('orphanPagination').classList.add('hidden');
                    return;
                }} else {{
                    document.getElementById('orphanDataTable').classList.remove('hidden');
                    document.getElementById('orphanTableEmpty').classList.add('hidden');
                    document.getElementById('orphanPagination').classList.remove('hidden');
                }}

                pageRows.forEach((row, rIdx) => {{
                    const tr = document.createElement('tr');
                    tr.className = `border-b border-slate-100 dark:border-slate-800/50 hover:bg-slate-50/50 dark:hover:bg-slate-800/10 transition-colors ${{(rIdx % 2 !== 0) ? 'bg-slate-50/20 dark:bg-slate-800/5' : ''}}`;
                    row.forEach(val => {{
                        const td = document.createElement('td');
                        td.className = 'px-4 py-3 text-slate-700 dark:text-slate-300 font-medium max-w-[200px] truncate';
                        const displayVal = val === null ? '[NULL]' : String(val);
                        td.innerText = displayVal;
                        td.title = displayVal;
                        tr.appendChild(td);
                    }});
                    body.appendChild(tr);
                }});

                // Pagination text & disabled states
                document.getElementById('orphanPageInfo').innerText = `Showing ${{(totalRows === 0) ? 0 : startIdx + 1}} to ${{endIdx}} of ${{totalRows}} rows (Page ${{orphanPage}} of ${{totalPages}})`;
                document.getElementById('orphanPrevBtn').disabled = orphanPage === 1;
                document.getElementById('orphanNextBtn').disabled = orphanPage === totalPages;
            }}

            function orphanPrevPage() {{
                if (orphanPage > 1) {{
                    orphanPage--;
                    renderOrphanTable();
                }}
            }}

            function orphanNextPage() {{
                let data = null;
                if (currentOrphanType === 'src_orphans') data = unmatchedSrcData;
                else if (currentOrphanType === 'tgt_orphans') data = unmatchedTgtData;
                else if (currentOrphanType === 'src_invalid') data = invalidSrcData;
                else if (currentOrphanType === 'tgt_invalid') data = invalidTgtData;
                const rows = data ? data.rows : [];
                let filtered = rows;
                if (orphanSearchText) {{
                    const term = orphanSearchText.toLowerCase();
                    filtered = rows.filter(r => r.some(val => val !== null && String(val).toLowerCase().includes(term)));
                }}
                const totalPages = Math.ceil(filtered.length / orphanPageSize) || 1;
                if (orphanPage < totalPages) {{
                    orphanPage++;
                    renderOrphanTable();
                }}
            }}

            // v3.0: Severity & Advanced Mismatch Filtering
            let currentSeverityFilter = 'all';
            let currentMismatchTypeFilter = 'all';

            function filterSeverity(level) {{
                currentSeverityFilter = level;
                document.querySelectorAll('.sev-filter-btn').forEach(b => {{
                    b.classList.remove('active');
                    b.style.borderColor = 'transparent';
                }});
                const activeBtn = document.querySelector(`[data-severity="${{level}}"]`);
                if (activeBtn) {{
                    activeBtn.classList.add('active');
                    activeBtn.style.borderColor = level === 'all' ? 'rgb(99,102,241)' : level === 'critical' ? 'rgb(239,68,68)' : level === 'warning' ? 'rgb(234,179,8)' : 'rgb(148,163,184)';
                }}
                applyMatrixFilters();
            }}

            function filterMismatchType() {{
                currentMismatchTypeFilter = document.getElementById('mismatchTypeFilter').value;
                applyMatrixFilters();
            }}

            function applyMatrixFilters() {{
                const matrixSearchInput = document.getElementById('matrixSearch');
                const term = matrixSearchInput ? matrixSearchInput.value.toLowerCase() : '';
                const rows = document.querySelectorAll('.matrix-row');
                
                rows.forEach(row => {{
                    const colName = row.querySelector('.col-name').innerText.toLowerCase();
                    const totalCell = row.querySelector('td:nth-last-child(2)');
                    const total = parseInt(totalCell.getAttribute('data-val'));
                    const accId = row.getAttribute('onclick').match(/'([^']+)'/)[1];
                    const accRow = document.getElementById(accId);
                    
                    let matchesSearch = colName.includes(term);

                    let matchesSeverity = false;
                    if (currentSeverityFilter === 'all') matchesSeverity = true;
                    else if (currentSeverityFilter === 'critical' && total > 1000) matchesSeverity = true;
                    else if (currentSeverityFilter === 'warning' && total > 100 && total <= 1000) matchesSeverity = true;
                    else if (currentSeverityFilter === 'info' && total <= 100) matchesSeverity = true;

                    let matchesMismatchType = false;
                    if (currentMismatchTypeFilter === 'all') {{
                        matchesMismatchType = true;
                    }} else {{
                        const colIdx = parseInt(currentMismatchTypeFilter);
                        const cell = row.children[colIdx];
                        const count = cell ? parseInt(cell.getAttribute('data-val') || '0') : 0;
                        if (count > 0) matchesMismatchType = true;
                    }}

                    const show = matchesSearch && matchesSeverity && matchesMismatchType;
                    row.style.display = show ? '' : 'none';
                    if (!show) {{
                        accRow.classList.add('hidden');
                        accRow.classList.remove('expanded');
                        const arrow = row.querySelector('.col-name span');
                        if (arrow) arrow.innerText = '▶';
                    }}
                }});

                updateActiveFiltersBadge();
                refreshZebra();
            }}

            function clearAllFilters() {{
                const matrixSearchInput = document.getElementById('matrixSearch');
                if (matrixSearchInput) {{
                    matrixSearchInput.value = '';
                    // We dispatch a custom event to update filtering, but to avoid triggering infinite clear loops,
                    // we update badge and filters manually.
                    matrixSearchInput.dispatchEvent(new Event('input'));
                }}

                currentSeverityFilter = 'all';
                document.querySelectorAll('.sev-filter-btn').forEach(b => {{
                    b.classList.remove('active');
                    b.style.borderColor = 'transparent';
                }});
                const activeBtn = document.querySelector(`[data-severity="all"]`);
                if (activeBtn) {{
                    activeBtn.classList.add('active');
                    activeBtn.style.borderColor = 'rgb(99,102,241)';
                }}

                const selectEl = document.getElementById('mismatchTypeFilter');
                if (selectEl) {{
                    selectEl.value = 'all';
                    currentMismatchTypeFilter = 'all';
                }}

                applyMatrixFilters();
                showToast('All filters cleared');
            }}

            function updateActiveFiltersBadge() {{
                const badge = document.getElementById('activeFiltersBadge');
                const textSpan = document.getElementById('activeFiltersText');
                const matrixSearchInput = document.getElementById('matrixSearch');
                const searchVal = matrixSearchInput ? matrixSearchInput.value : '';

                let filters = [];
                if (searchVal) filters.push('Search: "' + searchVal + '"');
                if (currentSeverityFilter !== 'all') filters.push('Severity: ' + currentSeverityFilter);
                if (currentMismatchTypeFilter !== 'all') {{
                    const selectEl = document.getElementById('mismatchTypeFilter');
                    const optionText = selectEl ? selectEl.options[selectEl.selectedIndex].text : '';
                    filters.push('Type: ' + optionText);
                }}

                if (filters.length > 0 && badge && textSpan) {{
                    badge.classList.remove('hidden');
                    textSpan.innerText = filters.join(' | ');
                }} else if (badge) {{
                    badge.classList.add('hidden');
                }}
            }}

            // v3.0: Expand All Accordions
            function expandAllAccordions() {{
                const rows = document.querySelectorAll('.matrix-row');
                rows.forEach(row => {{
                    if (row.style.display === 'none') return;
                    const accId = row.getAttribute('onclick').match(/'([^']+)'/)[1];
                    const accRow = document.getElementById(accId);
                    accRow.classList.remove('hidden');
                    accRow.classList.add('expanded');
                    const arrow = row.querySelector('.col-name span');
                    arrow.innerText = '▼';
                    arrow.classList.add('rotate-90');
                }});
            }}

            // v3.0: Collapse All Accordions
            function collapseAllAccordions() {{
                const allAccordions = document.querySelectorAll('.accordion-content');
                allAccordions.forEach(acc => {{
                    acc.classList.add('hidden');
                    acc.classList.remove('expanded');
                    const matrixRow = acc.previousElementSibling;
                    if (matrixRow) {{
                        const arrow = matrixRow.querySelector('.col-name span');
                        if (arrow) {{
                            arrow.innerText = '▶';
                            arrow.classList.remove('rotate-90');
                        }}
                    }}
                }});
            }}

            // v3.0: Toast Notification
            function showToast(message, type = 'success') {{
                const existing = document.getElementById('toast-notification');
                if (existing) existing.remove();

                const icon = type === 'success' 
                    ? '<svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
                    : '<svg class="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';

                const toast = document.createElement('div');
                toast.id = 'toast-notification';
                toast.className = 'fixed bottom-8 left-1/2 -translate-x-1/2 z-[999] toast-enter';
                toast.innerHTML = `
                    <div class="flex items-center gap-3 px-5 py-3 rounded-2xl shadow-2xl border text-sm font-bold
                        ${{htmlClass.contains('dark') ? 'bg-slate-800 border-slate-700 text-slate-200' : 'bg-white border-slate-200 text-slate-700'}}">
                        ${{icon}}
                        <span>${{message}}</span>
                    </div>
                `;
                document.body.appendChild(toast);

                setTimeout(() => {{
                    toast.classList.remove('toast-enter');
                    toast.classList.add('toast-exit');
                    setTimeout(() => toast.remove(), 300);
                }}, 2500);
            }}

            // Zebra Striping Refresh
            function refreshZebra() {{
                const rows = Array.from(document.querySelectorAll('.matrix-row')).filter(r => r.style.display !== 'none');
                rows.forEach((row, i) => {{
                    row.classList.remove('bg-slate-50/50', 'dark:bg-slate-800/20');
                    if (i % 2 !== 0 && !row.className.includes('bg-red') && !row.className.includes('bg-yellow')) {{
                        row.classList.add('bg-slate-50/50', 'dark:bg-slate-800/20');
                    }}
                }});
            }}

            // Search Logic
            document.getElementById('matrixSearch').addEventListener('input', function(e) {{
                applyMatrixFilters();
            }});

            // Sort Logic
            let sortDirections = new Array(18).fill(false);
            function sortTable(colIdx, isNumeric) {{
                const tbody = document.getElementById('matrixBody');
                const rows = Array.from(document.querySelectorAll('.matrix-row'));
                const dir = sortDirections[colIdx] ? 1 : -1;
                sortDirections[colIdx] = !sortDirections[colIdx];
                
                rows.sort((a, b) => {{
                    let valA, valB;
                    if (isNumeric) {{
                        valA = parseInt(a.children[colIdx].getAttribute('data-val'));
                        valB = parseInt(b.children[colIdx].getAttribute('data-val'));
                        return (valA - valB) * dir;
                    }} else {{
                        valA = a.children[colIdx].innerText.toLowerCase();
                        valB = b.children[colIdx].innerText.toLowerCase();
                        return valA.localeCompare(valB) * dir;
                    }}
                }});

                rows.forEach(row => {{
                    const accId = row.getAttribute('onclick').match(/'([^']+)'/)[1];
                    const accRow = document.getElementById(accId);
                    tbody.appendChild(row);
                    tbody.appendChild(accRow);
                }});
                refreshZebra();
            }}

            // Sidebar Toggle
            // Arrow paths: left = collapse (sidebar open), right = expand (sidebar closed)
            const ARROW_LEFT  = 'M15 19l-7-7 7-7';
            const ARROW_RIGHT = 'M9 5l7 7-7 7';

            function updateArrow(collapsed) {{
                const path = document.querySelector('#sidebar-toggle-icon path');
                if (path) path.setAttribute('d', collapsed ? ARROW_RIGHT : ARROW_LEFT);
            }}

            function toggleSidebar() {{
                const sidebar = document.getElementById('sidebar');
                sidebar.classList.toggle('collapsed');
                const isCollapsed = sidebar.classList.contains('collapsed');
                localStorage.sidebarCollapsed = isCollapsed;
                updateArrow(isCollapsed);
            }}

            // Column Hover Highlighting
            document.addEventListener('DOMContentLoaded', () => {{
                const table = document.querySelector('#matrix table');
                if (!table) return;

                table.addEventListener('mouseover', (e) => {{
                    const cell = e.target.closest('td, th');
                    if (!cell) return;

                    const colIdx = cell.cellIndex;
                    if (colIdx === 0 || colIdx >= cell.parentElement.children.length - 2) return;

                    const ths = table.querySelectorAll('thead tr th');
                    if (ths[colIdx]) ths[colIdx].classList.add('bg-indigo-500/10', 'dark:bg-indigo-400/10');

                    const matrixRows = table.querySelectorAll('.matrix-row');
                    matrixRows.forEach(row => {{
                        const td = row.cells[colIdx];
                        if (td) {{
                            td.classList.add('bg-indigo-500/5', 'dark:bg-indigo-400/5', 'border-x', 'border-indigo-500/20');
                        }}
                    }});
                }});

                table.addEventListener('mouseout', (e) => {{
                    const cell = e.target.closest('td, th');
                    if (!cell) return;

                    const colIdx = cell.cellIndex;
                    if (colIdx === 0 || colIdx >= cell.parentElement.children.length - 2) return;

                    const ths = table.querySelectorAll('thead tr th');
                    if (ths[colIdx]) ths[colIdx].classList.remove('bg-indigo-500/10', 'dark:bg-indigo-400/10');

                    const matrixRows = table.querySelectorAll('.matrix-row');
                    matrixRows.forEach(row => {{
                        const td = row.cells[colIdx];
                        if (td) {{
                            td.classList.remove('bg-indigo-500/5', 'dark:bg-indigo-400/5', 'border-x', 'border-indigo-500/20');
                        }}
                    }});
                }});
            }});

            // Initialization
            document.addEventListener('DOMContentLoaded', () => {{
                // Restore sidebar state
                const isCollapsed = localStorage.sidebarCollapsed === 'true';
                if (isCollapsed) {{
                    document.getElementById('sidebar').classList.add('collapsed');
                }}
                updateArrow(isCollapsed);
                animateCounters();
                refreshZebra();
                updateChartColors();

                // Initialize orphan/invalid table search and default tab
                const orphanSearchInput = document.getElementById('orphanSearch');
                if (orphanSearchInput) {{
                    orphanSearchInput.addEventListener('input', function(e) {{
                        orphanSearchText = e.target.value;
                        orphanPage = 1;
                        renderOrphanTable();
                    }});
                }}
                switchOrphanTable('src_orphans');
            }});

            function getMatrixData() {{
                const rows = Array.from(document.querySelectorAll('.matrix-row'));
                let csv = "Field,Source Value is NULL,Target Value is NULL,Null Equivalent Mismatch,Duplicate Value Mismatch,Sorting Issue,Whitespace Mismatch,Case Sensitivity Mismatch,Type Coercion / Formatting,Boolean Format Mismatch,Encoding / Special Char Mismatch,Precision / Rounding,Data Truncation,Date/Timestamp Mismatch,Numeric Data Mismatch,String Data Mismatch,Total Issues,% Total\\r\\n";
                rows.forEach(row => {{
                    if(row.style.display !== 'none') {{
                        const cols = Array.from(row.children).map(c => c.getAttribute('data-val') || c.innerText.replace('▶', '').replace('▼', '').trim());
                        csv += cols.map(c => `"${{c}}"`).join(",") + "\\r\\n";
                    }}
                }});
                return csv;
            }}

            function exportCSV() {{
                const csv = '\\ufeff' + getMatrixData();
                const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `tosca_integrity_report_${{new Date().toISOString().slice(0,10).replace(/-/g,'')}}.csv`;
                a.click();
                showToast('CSV exported successfully');
            }}

            function copySqlToClipboard(elementId) {{
                const sqlText = document.getElementById(elementId).innerText;
                navigator.clipboard.writeText(sqlText).then(() => {{
                    showToast('SQL query copied to clipboard');
                }});
            }}

            function copyToClipboard() {{
                const rows = Array.from(document.querySelectorAll('.matrix-row'));
                let text = "Field\\tSource Value is NULL\\tTarget Value is NULL\\tNull Equivalent Mismatch\\tDuplicate Value Mismatch\\tSorting Issue\\tWhitespace Mismatch\\tCase Sensitivity Mismatch\\tType Coercion / Formatting\\tBoolean Format Mismatch\\tEncoding / Special Char Mismatch\\tPrecision / Rounding\\tData Truncation\\tDate/Timestamp Mismatch\\tNumeric Data Mismatch\\tString Data Mismatch\\tTotal Issues\\t% Total\\n";
                rows.forEach(row => {{
                    if(row.style.display !== 'none') {{
                        const cols = Array.from(row.children).map(c => c.getAttribute('data-val') || c.innerText.replace(/[\u25b6\u25bc]/g, '').trim());
                        text += cols.join("\\t") + "\\n";
                    }}
                }});
                navigator.clipboard.writeText(text).then(() => {{
                    showToast('Matrix data copied to clipboard');
                }});
            }}

        </script>
    </body>
    </html>
    """
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    conn.close()
    print(f"Final Consolidated Dashboard Generated: {output_html}")

if __name__ == "__main__":
    db_name = "SFT CQAV3.0 QA - Informa vs D1_MIPRANS_OWNER.GC_SFP_HC_DS_ALL_DATA_20260410165257.db"
    row_keys = ['col1', 'col2', 'col3', 'col4', 'col5']
    generate_unified_dashboard(db_name, row_keys=row_keys)





