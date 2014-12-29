# enrollments/form.py

from flask_wtf import Form
from wtforms import SelectField, SelectMultipleField, widgets, RadioField, TextField, validators
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
    classNumber = TextField('Class Number', validators=[validators.required(message="Class number is required."),
        validators.Regexp(regex=r'\d{5}', message="Please double check the class number.")])
    sessionLength = SelectField('Session Length',
        default='14W',
        validators=[validators.required()],
        choices=[
            ('8W', 'Eight Week'),
            ('4W1', 'Four Week - First'),
            ('4W2', 'Four Week - Second'),
            ('14W', 'Fourteen Week'),
            ('7W1', 'Seven Week - First'),
            ('7W2', 'Seven Week - Second'),
            ('17W', 'Seventeen Week'),
            ('10W', 'Ten Week'),
            ('3WI', 'Three Week Interim')
            ])
    subject = TextField('Subject Code', validators=[validators.required(message="Subject code is required."),
        validators.Regexp(regex=r'[a-zA-Z ]{3,8}', message="Please double check the subject.")])
    catalogNumber = TextField('Catalog Number', validators=[validators.required(message="Catalog Number is required."),
        validators.Regexp(regex=r'\d{3}', message="Please double check the catalog number.")])
    section = TextField('First 4-digits of section', validators=[validators.required(message="Section is required."),
        validators.Regexp(regex=r'\d{3}[a-zA-Z]{1}', message="Please double check the section.")])