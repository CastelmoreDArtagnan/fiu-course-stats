import pandas as pd
import json
import numpy as np

def get_stats_rank(gpa, gpa_list):
    """Calculates rank based on percentiles, ignoring blanks/NaNs."""
    valid_gpas = [g for g in gpa_list if not pd.isna(g)]
    if not valid_gpas or len(set(valid_gpas)) <= 1:
        return "N/A"
    
    p60 = np.percentile(valid_gpas, 60) # Top 40%
    p30 = np.percentile(valid_gpas, 30) # Bottom 30%
    
    if gpa >= p60: return "A"
    elif gpa >= p30: return "B"
    else: return "C"

def build_database():
    print("Loading 300,000+ row dataset into RAM...")
    df = pd.read_csv('fiu_master_grade_distribution.csv', dtype=str)
    
    # 1. Clean the column names (Tableau leaves spaces like 'Academic Year ')
    df.columns = df.columns.str.strip()
    
    print("Formatting and removing duplicates...")
    # Drop rows without actual metric values
    df.dropna(subset=['Measure Values'], inplace=True)
    df['Measure Values'] = pd.to_numeric(df['Measure Values'], errors='coerce')
    
    # If the scraper accidentally duplicated a professor, this drops the duplicate rows
    df.drop_duplicates(subset=['Academic Year', 'Course Listing', 'Measure Names', 'Professor'], inplace=True)
    
    print("Pivoting data to align grade columns...")
    # Pivot the data so 'A Grades', 'B Grades', etc. become their own columns
    pivot_df = df.pivot(
        index=['Academic Year', 'Course Listing', 'Professor'], 
        columns='Measure Names', 
        values='Measure Values'
    ).reset_index()
    
    # Extract Department Code
    pivot_df['Department'] = pivot_df['Course Listing'].str.extract(r'^([A-Z]{3,4})')
    
    # Ensure all grade columns exist and fill blanks with 0
    grade_cols = ['A Grades', 'B Grades', 'C Grades', 'D Grades', 'F Grades']
    for col in grade_cols:
        if col not in pivot_df.columns:
            pivot_df[col] = 0
        pivot_df[col] = pivot_df[col].fillna(0)

    print("Calculating True GPAs...")
    # Combine all academic years together for a true historical view of the professor per course
    prof_course = pivot_df.groupby(['Department', 'Course Listing', 'Professor']).agg({
        'A Grades': 'sum', 'B Grades': 'sum', 'C Grades': 'sum', 'D Grades': 'sum', 'F Grades': 'sum'
    }).reset_index()
    
    # Calculate Grade Points
    prof_course['Total Graded'] = prof_course['A Grades'] + prof_course['B Grades'] + prof_course['C Grades'] + prof_course['D Grades'] + prof_course['F Grades']
    prof_course['Total Points'] = (prof_course['A Grades']*4 + prof_course['B Grades']*3 + prof_course['C Grades']*2 + prof_course['D Grades']*1)
    
    # Calculate GPA (Handling division by zero if nobody actually got graded)
    prof_course['GPA'] = np.where(prof_course['Total Graded'] > 0, prof_course['Total Points'] / prof_course['Total Graded'], np.nan)

    # Roll up data to the Course level
    course_agg = prof_course.groupby(['Department', 'Course Listing']).agg({'Total Graded': 'sum', 'Total Points': 'sum'}).reset_index()
    course_agg['GPA'] = np.where(course_agg['Total Graded'] > 0, course_agg['Total Points'] / course_agg['Total Graded'], np.nan)
    
    # Roll up data to the Department level
    dept_agg = course_agg.groupby('Department').agg({'Total Graded': 'sum', 'Total Points': 'sum'}).reset_index()
    dept_agg['GPA'] = np.where(dept_agg['Total Graded'] > 0, dept_agg['Total Points'] / dept_agg['Total Graded'], np.nan)

    print("Building JSON Database...")
    database = {"departments": {}}

    for dept in dept_agg['Department'].dropna():
        dept_info = dept_agg[dept_agg['Department'] == dept].iloc[0]
        database["departments"][dept] = {
            "department_gpa": f"{dept_info['GPA']:.2f}" if not pd.isna(dept_info['GPA']) else "N/A",
            "courses": {}
        }
        
        # Get all courses for this department to calculate percentiles
        dept_courses = course_agg[course_agg['Department'] == dept]
        dept_gpas = dept_courses['GPA'].tolist()
        
        for _, c_row in dept_courses.iterrows():
            course_code = c_row['Course Listing']
            c_gpa = c_row['GPA']
            
            database["departments"][dept]["courses"][course_code] = {
                "historic_gpa": f"{c_gpa:.2f}" if not pd.isna(c_gpa) else "N/A",
                "stats_rank": get_stats_rank(c_gpa, dept_gpas),
                "spot_score": "N/A",
                "professors": {}
            }
            
            # Get professors for this course to calculate percentiles
            course_profs = prof_course[prof_course['Course Listing'] == course_code]
            prof_gpas = course_profs['GPA'].tolist()
            
            for _, p_row in course_profs.iterrows():
                prof_name = p_row['Professor']
                p_gpa = p_row['GPA']
                
                # Calculate the percentage of students who got an A or B
                total = p_row['Total Graded']
                a_pct = f"{(p_row['A Grades'] / total * 100):.1f}%" if total > 0 else "N/A"
                b_pct = f"{(p_row['B Grades'] / total * 100):.1f}%" if total > 0 else "N/A"
                
                # If they never gave an A/B/C/D/F grade, skip showing them in the UI
                if total == 0: continue 

                database["departments"][dept]["courses"][course_code]["professors"][prof_name] = {
                    "overall_gpa": f"{p_gpa:.2f}" if not pd.isna(p_gpa) else "N/A",
                    "stats_rank": get_stats_rank(p_gpa, prof_gpas),
                    "total_graded": int(total),
                    "a_pct": a_pct,
                    "b_pct": b_pct
                }

    print("Exporting finalized hierarchical JSON database...")
    with open('fiu_data.json', 'w') as f:
        json.dump(database, f, indent=4)
        
    print("Backend processing complete! Ready for UI.")

if __name__ == "__main__":
    build_database()