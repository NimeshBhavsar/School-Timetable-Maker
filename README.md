# School Timetable Maker

A minimal Python timetable app for schools.

## Features
- Fixed school day structure: 5 periods, break, then 5 periods
- Edit timetable by class/section or by teacher
- View class timetable and teacher timetable
- Import/export timetable data as JSON
- Simple conflict checking for teacher clashes

## Run
1. Install dependencies
2. Run:
   ```bash
   streamlit run app.py
   ```

## Cell format
- Class editor: `Subject | Teacher`
- Teacher editor: `Class-Section | Subject`

## Data format
Teachers can be assigned multiple subjects in the sidebar:
- `Mr. Sharma: Math, Science`
- `Ms. Khan: English, Hindi`
