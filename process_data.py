import pandas as pd
import json
import numpy as np

# --- GPA COLUMN CONFIGURATION ---
COL_COURSE = 'Course Listing'     
COL_TERM = 'Semester'             
COL_GPA = 'Average GPA'           
COL_PROF = 'Professor'            

# --- SPOT COLUMN CONFIGURATION ---
SPOT_FILE = 'fiu_spots_data.csv'   
SPOT_COL_COURSE = 'Subject + Catalog'         
SPOT_COL_TITLE = 'Course Name'    
SPOT_COL_PROF = 'Instructor Name'       
SPOT_COL_EXC = 'Excellent'
SPOT_COL_VG = 'Very Good'
SPOT_COL_GOOD = 'Good'
SPOT_COL_FAIR = 'Fair'
SPOT_COL_POOR = 'Poor'

def get_stats_rank(score, score_list):
    """Calculates A/B/C rank, safely ignoring any N/A or NaN values."""
    valid_scores = [s for s in score_list if not pd.isna(s) and s != "N/A"]
    if not valid_scores or len(set(valid_scores)) <= 1 or pd.isna(score) or score == "N/A": 
        return "N/A"
    
    p60 = np.percentile(valid_scores, 60)
    p30 = np.percentile(valid_scores, 30)
    
    if score >= p60: return "A"
    elif score >= p30: return "B"
    else: return "C"

def flip_name(name):
    """Detects 'Lastname, Firstname' and flips it to 'Firstname Lastname'."""
    name = str(name).strip()
    if ',' in name:
        parts = name.split(',')
        return f"{parts[1].strip()} {parts[0].strip()}"
    return name

def clean_pct(series):
    """Strips % signs and converts text percentages to raw numbers."""
    return pd.to_numeric(series.astype(str).str.replace('%', '', regex=False), errors='coerce').fillna(0)

def robust_csv_load(filepath):
    """Smart loader that tests multiple encodings and separators to crack large exports."""
    encodings = ['utf-8', 'utf-16', 'utf-8-sig', 'latin1']
    separators = [',', '\t']
    
    for enc in encodings:
        for sep in separators:
            try:
                # on_bad_lines='skip' ensures that 1 broken row out of 300,000 won't crash the script
                df = pd.read_csv(filepath, dtype=str, encoding=enc, sep=sep, on_bad_lines='skip')
                # If it successfully split the data into multiple columns, we found the right combo!
                if len(df.columns) > 1:
                    print(f"  -> Success! Unlocked file using Encoding: {enc} | Separator: '{sep}'")
                    return df
            except Exception:
                continue
    raise ValueError(f"Could not decode {filepath}. Please open it in Excel and 'Save As -> CSV (Comma delimited)'")

def build_database():
    print("Loading GPA Database...")
    try:
        gpa_df = robust_csv_load('fiu_master_grade_distribution.csv')
        gpa_df.columns = gpa_df.columns.str.strip()
        gpa_df.dropna(subset=['Measure Values'], inplace=True)
        gpa_df['Measure Values'] = pd.to_numeric(gpa_df['Measure Values'], errors='coerce')
        gpa_df.drop_duplicates(subset=['Academic Year', 'Course Listing', 'Measure Names', 'Professor'], inplace=True)
        
        pivot_df = gpa_df.pivot(index=['Academic Year', 'Course Listing', 'Professor'], columns='Measure Names', values='Measure Values').reset_index()
        pivot_df['Department'] = pivot_df['Course Listing'].str.extract(r'^([A-Z]{3,4})')
        
        for col in ['A Grades', 'B Grades', 'C Grades', 'D Grades', 'F Grades']:
            if col not in pivot_df.columns: pivot_df[col] = 0
            pivot_df[col] = pivot_df[col].fillna(0)

        prof_course = pivot_df.groupby(['Department', 'Course Listing', 'Professor']).agg({
            'A Grades': 'sum', 'B Grades': 'sum', 'C Grades': 'sum', 'D Grades': 'sum', 'F Grades': 'sum'
        }).reset_index()
        
        prof_course['Total Graded'] = prof_course['A Grades'] + prof_course['B Grades'] + prof_course['C Grades'] + prof_course['D Grades'] + prof_course['F Grades']
        prof_course['Total Points'] = (prof_course['A Grades']*4 + prof_course['B Grades']*3 + prof_course['C Grades']*2 + prof_course['D Grades']*1)
        prof_course['GPA'] = np.where(prof_course['Total Graded'] > 0, prof_course['Total Points'] / prof_course['Total Graded'], np.nan)

        course_agg = prof_course.groupby(['Department', 'Course Listing']).agg({'Total Graded': 'sum', 'Total Points': 'sum'}).reset_index()
        course_agg['GPA'] = np.where(course_agg['Total Graded'] > 0, course_agg['Total Points'] / course_agg['Total Graded'], np.nan)
        dept_agg = course_agg.groupby('Department').agg({'Total Graded': 'sum', 'Total Points': 'sum'}).reset_index()
        dept_agg['GPA'] = np.where(dept_agg['Total Graded'] > 0, dept_agg['Total Points'] / dept_agg['Total Graded'], np.nan)
        
        dept_gpa_dict = dept_agg.set_index('Department')['GPA'].to_dict()
        course_gpa_dict = course_agg.set_index('Course Listing')['GPA'].to_dict()
        prof_course_dict = prof_course.set_index(['Course Listing', 'Professor']).to_dict('index')

    except Exception as e:
        print(f"Error loading GPA data: {e}")
        dept_gpa_dict, course_gpa_dict, prof_course_dict, prof_course = {}, {}, {}, pd.DataFrame()

    print("Loading SPOTs Database (This might take a moment for 400MB)...")
    try:
        spots_df = robust_csv_load(SPOT_FILE)
        spots_df.columns = spots_df.columns.str.strip()
        spots_df[SPOT_COL_PROF] = spots_df[SPOT_COL_PROF].apply(flip_name)
        spots_df['Department'] = spots_df[SPOT_COL_COURSE].str.extract(r'^([A-Z]{3,4})')
        
        spots_df[SPOT_COL_EXC] = clean_pct(spots_df[SPOT_COL_EXC])
        spots_df[SPOT_COL_VG] = clean_pct(spots_df[SPOT_COL_VG])
        spots_df[SPOT_COL_GOOD] = clean_pct(spots_df[SPOT_COL_GOOD])
        spots_df[SPOT_COL_FAIR] = clean_pct(spots_df[SPOT_COL_FAIR])
        spots_df[SPOT_COL_POOR] = clean_pct(spots_df[SPOT_COL_POOR])
        
        spots_df['Calculated_Score'] = (
            (spots_df[SPOT_COL_EXC] * 1.0) + (spots_df[SPOT_COL_VG] * 0.8) +
            (spots_df[SPOT_COL_GOOD] * 0.6) + (spots_df[SPOT_COL_FAIR] * 0.35) + (spots_df[SPOT_COL_POOR] * 0.0)
        )
        
        course_titles = spots_df.drop_duplicates(subset=[SPOT_COL_COURSE]).set_index(SPOT_COL_COURSE)[SPOT_COL_TITLE].to_dict()
        prof_course_spot = spots_df.groupby([SPOT_COL_COURSE, SPOT_COL_PROF])['Calculated_Score'].mean().to_dict()
        prof_global_spot = spots_df.groupby(SPOT_COL_PROF)['Calculated_Score'].mean().to_dict()
        course_global_spot = spots_df.groupby(SPOT_COL_COURSE)['Calculated_Score'].mean().to_dict()
    except Exception as e:
        print(f"Error loading SPOTs data: {e}")
        spots_df, course_titles, prof_course_spot, prof_global_spot, course_global_spot = pd.DataFrame(), {}, {}, {}, {}

    print("Merging Universes (Building Master Hierarchy)...")
    master_hierarchy = {}

    if not prof_course.empty:
        for _, row in prof_course.iterrows():
            d, c, p = row['Department'], row['Course Listing'], row['Professor']
            if pd.isna(d): continue
            if d not in master_hierarchy: master_hierarchy[d] = {}
            if c not in master_hierarchy[d]: master_hierarchy[d][c] = set()
            master_hierarchy[d][c].add(p)

    if not spots_df.empty:
        for _, row in spots_df.iterrows():
            d, c, p = row['Department'], row[SPOT_COL_COURSE], row[SPOT_COL_PROF]
            if pd.isna(d) or pd.isna(c): continue
            if d not in master_hierarchy: master_hierarchy[d] = {}
            if c not in master_hierarchy[d]: master_hierarchy[d][c] = set()
            master_hierarchy[d][c].add(p)

    print("Building JSON Database...")
    database = {"departments": {}, "professors": {}}

    all_global_spots = [s for s in prof_global_spot.values() if not pd.isna(s)]
    for prof, score in prof_global_spot.items():
        if not pd.isna(score):
            database["professors"][prof] = {
                "global_spot": f"{score:.1f}%", 
                "spot_rank": get_stats_rank(score, all_global_spots)
            }

    for dept, courses in master_hierarchy.items():
        d_gpa = dept_gpa_dict.get(dept, np.nan)
        database["departments"][dept] = {
            "department_gpa": f"{d_gpa:.2f}" if not pd.isna(d_gpa) else "N/A",
            "courses": {}
        }
        
        dept_course_gpas = [course_gpa_dict.get(c, np.nan) for c in courses.keys()]
        dept_course_spots = [course_global_spot.get(c, np.nan) for c in courses.keys()]
        
        for course, profs in courses.items():
            c_gpa = course_gpa_dict.get(course, np.nan)
            c_spot = course_global_spot.get(course, np.nan)
            title = course_titles.get(course, "")
            
            database["departments"][dept]["courses"][course] = {
                "course_name": title,
                "historic_gpa": f"{c_gpa:.2f}" if not pd.isna(c_gpa) else "N/A",
                "stats_rank": get_stats_rank(c_gpa, dept_course_gpas),
                "spot_score": f"{c_spot:.1f}%" if not pd.isna(c_spot) else "N/A",
                "spot_rank": get_stats_rank(c_spot, dept_course_spots),
                "professors": {}
            }
            
            prof_gpas = [prof_course_dict.get((course, p), {}).get('GPA', np.nan) for p in profs]
            prof_spots = [prof_course_spot.get((course, p), np.nan) for p in profs]
            
            for prof in profs:
                p_spot = prof_course_spot.get((course, prof), np.nan)
                p_gpa_data = prof_course_dict.get((course, prof), {})
                
                p_gpa = p_gpa_data.get('GPA', np.nan)
                total = p_gpa_data.get('Total Graded', 0)
                
                if total > 0:
                    a_pct = f"{(p_gpa_data.get('A Grades', 0) / total * 100):.1f}%"
                    b_pct = f"{(p_gpa_data.get('B Grades', 0) / total * 100):.1f}%"
                    total_str = str(int(total))
                else:
                    a_pct = "N/A"
                    b_pct = "N/A"
                    total_str = "N/A"

                database["departments"][dept]["courses"][course]["professors"][prof] = {
                    "overall_gpa": f"{p_gpa:.2f}" if not pd.isna(p_gpa) else "N/A",
                    "stats_rank": get_stats_rank(p_gpa, prof_gpas),
                    "spot_score": f"{p_spot:.1f}%" if not pd.isna(p_spot) else "N/A",
                    "spot_rank": get_stats_rank(p_spot, prof_spots),
                    "total_graded": total_str,
                    "a_pct": a_pct,
                    "b_pct": b_pct
                }

    print("Exporting finalized hierarchical JSON database...")
    with open('fiu_data.json', 'w') as f:
        json.dump(database, f, indent=4)
        
    print("Backend processing complete! Ready for UI.")

if __name__ == "__main__":
    build_database()