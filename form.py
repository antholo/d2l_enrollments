# enrollments/form.py

from flask_wtf import Form
from wtforms import SelectField, SelectMultipleField, widgets, RadioField, TextField
from datetime import date

# semester values for four-digit semester codes
FALL = '0'
SPRING = '5'
SUMMER = '8'

# base year for calculating semester code
BASE_YEAR = 1945


class SelectSemesterForm(Form):
	semester = SelectField('Select semester', choices=[('Fall', 'Fall'), ('Spring', 'Spring'), ('Summer', 'Summer')])
	year = SelectField('Select year', choices=[(str(year - BASE_YEAR), str(year)) for year in range(date.today().year - 1, date.today().year + 1)])


class SelectCoursesForm(Form):
	courseIds = SelectMultipleField('Courses', 
		widget=widgets.ListWidget(prefix_label=False),
		option_widget=widgets.CheckboxInput(),
		coerce=int)
	baseCourse = RadioField('Select base course')

class AdditionalCourseForm(Form):
	termCode = TextField('Term Code')
	duration = TextField('Duration')
	subject = TextField('Subject')
	catalog = TextField('Catalog Number')
	section = TextField('Section')
	classNumber = TextField('Class Number')
	courseTitle = TextField('Course Title')