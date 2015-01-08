# enrollments/views.py

from flask import Flask, render_template, request, session, flash, redirect, url_for
from flask_mail import Mail, Message
from flask_wtf.csrf import CsrfProtect
from functools import wraps
from form import SelectSemesterForm, SelectCoursesForm, AdditionalCourseForm
import requests
import os
import auth2 as d2lauth


##########
# config #
##########


app = Flask(__name__)
app.config.from_pyfile('app_config.cfg')
mail = Mail(app)
app.secret_key = os.urandom(24)
CsrfProtect(app)

appContext = d2lauth.fashion_app_context(app_id=app.config['APP_ID'],
                                         app_key=app.config['APP_KEY'])



############
# wrappers #
############


def login_required(test):
    @wraps(test)
    def wrap(*args, **kwargs):
        if 'userContext' in session:
            return test(*args, **kwargs)
        else:
            flash('You need to login first.')
            return redirect(url_for('login'))
    return wrap


##########
# routes #
##########


@app.route('/logout')
@login_required
def logout():
    '''
    Clears stored session information.
    '''
    session.clear()
    return redirect(app.config['REDIRECT_AFTER_LOGOUT'])


@app.route('/')
@app.route('/login')
def login():
    '''
    Checks if user context is stored in session and redirects to authorization
    handler if it is. If not, renders login template with link to D2L login and
    callback route to authorization handler.
    '''
    if 'userContext' in session:
        return redirect(url_for(app.config['AUTH_ROUTE']))
    else:
        authUrl = appContext.create_url_for_authentication(
            host=app.config['LMS_HOST'], 
            client_app_url=app.config['AUTH_CB'],
            encrypt_request=app.config['ENCRYPT_REQUESTS'])
        return render_template('login.html', authUrl=authUrl)


@app.route(app.config['AUTH_ROUTE'])
def auth_handler():
    '''
    Creates and stores user context and details.
    '''
    uc = appContext.create_user_context(
        result_uri=request.url, 
        host=app.config['LMS_HOST'],
        encrypt_requests=app.config['ENCRYPT_REQUESTS'])
    my_url = uc.create_authenticated_url(
        '/d2l/api/lp/{0}/users/whoami'.format(app.config['VER']))
    r = requests.get(my_url)

    session['firstName'] = r.json()['FirstName']
    session['lastName'] = r.json()['LastName']
    session['userId'] = r.json()['Identifier']

    """PRODUCTION: UNCOMMENT FOLLOWING LINE AND DELETE THE ONE AFTER THAT"""
    #session['uniqueName'] = r.json()['UniqueName']
    session['uniqueName'] = 'lookerb'

    # feed in service account ID and key and store user context
    uc.user_id = app.config['USER_ID']
    uc.user_key = app.config['USER_KEY']
    session['userContext'] = uc.get_context_properties()

    # get the dictionary of user's enrollments
    if 'courseDict' not in session:
        session['courseDict'] = get_courses(uc)
    return redirect(url_for('select_semester'))


@app.route('/semester', methods=['GET', 'POST'])
@login_required
def select_semester():
    '''
    Generates form with semester options for user to select.
    '''
    error = None
    form = SelectSemesterForm(request.form)
    if 'semCode' in session:
        session.pop('semCode')
    if 'coursesToCombine' in session:
        session.pop('coursesToCombine')
    if request.method == 'POST':
        if form.validate_on_submit():
            semCode = get_semester(form.semester.data, form.year.data)
            session['semCode'] = semCode

            try:
                courseDict = session['courseDict'][semCode]
            except KeyError:
                error = "No courses are listed with you enrolled" + \
                    "as an instructor for the selected semester."
                return render_template("semester.html", form=form, error=error)
        return redirect(url_for('enrollment_handler'))
    else:
        return render_template("semester.html", form=form, error=error)


@app.route('/enrollments', methods=['GET', 'POST'])
@login_required
def enrollment_handler():
    '''
    Generates forms with courses to select for combining and to add more
    courses to that list. 
    '''
    error = None
    uc = appContext.create_user_context(
        d2l_user_context_props_dict=session['userContext'])
    courseDict = session['courseDict'][session['semCode']]
    form = SelectCoursesForm(request.form, prefix="form")
    form.courseIds.choices = get_courseId_choices(courseDict)
    form.baseCourse.choices = get_baseCourse_choices(courseDict)
    add_form = AdditionalCourseForm(request.form, prefix="add_form")
    if request.method == 'POST':
        if form.is_submitted():
            if request.form['btn'] == 'Add Class' and add_form.validate_on_submit():
                code = make_code(add_form)
                courseToAdd = get_course(uc, code)
                if not courseToAdd:
                    error = "Please check course details and try again."
                    return render_template("enrollments.html", form=form, add_form=add_form, error=error)
                session['courseDict'][session['semCode']] = update_course_dict(courseDict,
                    courseToAdd['Identifier'],
                    courseToAdd['Name'],
                    code)
                return redirect(url_for('enrollment_handler'))
            elif request.form['btn'] == 'Add Class':
                error = add_form.errors.values()[0][0]
                return render_template("enrollments.html", form=form, add_form=add_form, error=error)
            elif request.form['btn'] == 'Submit Request':
                courseIds = form.courseIds.data
                coursesToCombine = [course for course in courseDict if course['courseId'] in courseIds]
                baseCourse = {}
                if form.baseCourse.data != 'None':
                    update_base_course(baseCourse, form.baseCourse.data, courseDict)
                else:
                    error = 'You must select a base course into which to combine the courses.'
                    return render_template("enrollments.html", form=form, add_form=add_form, error=error)
                if len(coursesToCombine) == 0 or (len(coursesToCombine) == 1 and baseCourse in coursesToCombine):    
                    error = 'You must select at least two courses to combine.'
                    return render_template("enrollments.html", form=form, add_form=add_form, error=error)
                session['baseCourse'], session['coursesToCombine'] = baseCourse, coursesToCombine
                if baseCourse not in coursesToCombine:
                    coursesToCombine.append(baseCourse)
                    return render_template("check.html", coursesToCombine=coursesToCombine, baseCourse=baseCourse)
                else:
                    return redirect(url_for('confirm_selections'))
        else:
            error = 'The form must be invalid for some reason...'
            return render_template("enrollments.html", form=form, add_form=add_form, error=error)
    else:
        return render_template("enrollments.html", form=form, add_form=add_form, error=error)


@app.route('/confirmation')
@login_required
def confirm_selections():
    '''
    Generates confirmation page and sends confirmation emails.
    '''
    msg = Message(subject='Course Combine Confirmation',
        recipients=[app.config['MAIL_DEFAULT_SENDER'],
        session['uniqueName'] + "@" app.config['EMAIL_DOMAIN']])
    msg.body = generate_msg_text(session['firstName'],
        session['lastName'],
        session['coursesToCombine'],
        session['baseCourse'])
    msg.html = generate_msg_html(session['firstName'],
        session['lastName'],
        session['coursesToCombine'],
        session['baseCourse'])
    mail.send(msg)
    return render_template("confirmation.html", coursesToCombine=session['coursesToCombine'], baseCourse=session['baseCourse'])


###########
# helpers #
###########


def generate_msg_text(firstName, lastName, coursesToCombine, baseCourse):
    '''
    Generates confirmation email message text.
    ''' 
    greeting = "Hello {0} {1},\n".format(firstName, lastName)
    opening = "You have asked to have the following courses combined into " + \
        "{0}, {1}:\n\nCourse Name\t(Course Id)\n".format(baseCourse['parsed'],
        baseCourse['name'])
    courseTable = "\n".join("{!s}\t({!s})".format(course['name'],
        course['code']) for course in coursesToCombine)
    closing = "\nIf this is incorrect, please contact our D2L site" + \
        "administrator at " + app.config['EMAIL_SITE_ADMIN'] + "."
    msg_body = greeting + opening + courseTable + closing
    return msg_body


def generate_msg_html(firstName, lastName, coursesToCombine, baseCourse):
    '''
    Generates confirmation email message in HTML.
    '''
    greeting = "<p>Hello {0} {1},</p><p>".format(firstName, lastName)
    opening = "You have asked to have the following courses combined into " +\
        " {0}, {1}:</p>".format(baseCourse['parsed'], baseCourse['name'])
    tableHead = "<table><thead><tr><th>Course Name</th><th>(Course Id)</th></thead>"
    courseTable = "".join("<tr><td>{!s}</td><td>({!s})</td></tr>".format(
        course['name'], course['code']) for course in coursesToCombine)
    tableClose = "</table>"
    closing = "<p>If this is incorrect, please contact our D2L site" + \
        "administrator at " + app.config['EMAIL_SITE_ADMIN'] + ".</p>"
    msg_html = greeting + opening + tableHead + courseTable + tableClose + closing
    return msg_html


def get_semester(semester, year):
    '''
    Determines semester code for UWO courses.
    '''
    if semester == 'Fall':
        precedingDigits = year
        finalDigit = app.config['FALL']
    if semester == 'Spring':
        precedingDigits = str(int(year) - 1)
        finalDigit = app.config['SPRING']
    if semester == 'Summer':
        precedingDigits = str(int(year) - 1)
        finalDigit = app.config['SUMMER']
    semesterCode = precedingDigits + finalDigit
    while len(semesterCode) < 4:
        semesterCode = '0' + semesterCode
    return semesterCode


def get_courses(uc):
    '''
    Creates dictionary of lists of courses keyed by semester code and stores 
    it in session for easy access post-creation.
    '''
    myUrl = uc.create_authenticated_url(
        '/d2l/api/lp/{0}/enrollments/users/{1}/orgUnits/'.format(
        app.config['VER'], session['userId']))
    kwargs = {'params': {}}
    kwargs['params'].update({'roleId':app.config['ROLE_ID']})
    kwargs['params'].update({'orgUnitTypeId': app.config['ORG_UNIT_TYPE_ID']})
    r = requests.get(myUrl, **kwargs)
    courseDict = {}
    end = False
    while end == False:
        for course in r.json()['Items']:
            semCode = str(course['OrgUnit']['Code'][6:10])
            if semCode.isdigit():
                if semCode not in courseDict:
                    courseDict[semCode] = []
                courseDict[semCode] = update_course_dict(courseDict[semCode],
                    course['OrgUnit']['Id'],
                    course['OrgUnit']['Name'],
                    course['OrgUnit']['Code'])

            if r.json()['PagingInfo']['HasMoreItems'] == True:
                kwargs['params']['bookmark'] = r.json()['PagingInfo']['Bookmark']
                r = requests.get(myUrl, **kwargs)
        else:
            end = True
    return courseDict


def update_course_dict(courseDict, courseId, name, code):
    '''
    Adds a course's info to the courseDict.
    '''
    courseDict.append({u'courseId': int(courseId),
        u'name': name,
        u'code': code,
        u'parsed': parse_code(code)})
    return courseDict


def get_course(uc, code):
    '''
    Gets course information for supplied code from D2L.
    '''
    myUrl = uc.create_authenticated_url('/d2l/api/lp/{0}/orgstructure/'.format(app.config['VER']))
    kwargs = {'params': {}}
    kwargs['params'].update({'orgUnitCode': code})
    kwargs['params'].update({'orgUnitType': app.config['ORG_UNIT_TYPE_ID']})
    r = requests.get(myUrl, **kwargs)
    try:
        return r.json()['Items'][0]
    except IndexError:
        return False


def parse_code(code):
    '''
    Breaks up code into more readable version to present to user.
    '''
    parsed = code.split("_")
    return parsed[3] + " " + parsed[4] + " " + parsed[5]


def get_courseId_choices(courseDict):
    '''
    Pulls elements from courseDict to use in form choices.
    '''
    return [(course['courseId'], 
        course['name'] + ", " + course['parsed']) for course in courseDict]


def get_baseCourse_choices(courseDict):
    '''
    Pulls elements from courseDict to use in baseCourse choices, with markup to
    make choices linkable.
    '''
    linkPrefix = "<a target=\"_blank\" href='http://" + \
        app.config['LMS_HOST'] + \
        "/d2l/lp/manageCourses/course_offering_info_viewedit.d2l?ou="

    return [(course['courseId'],
        linkPrefix +
        str(course['courseId']) +
        "'>" +
        course['name'] +
        ", " +
        course['parsed'] +
        "</a>") for course in courseDict]


def make_code(add_form):
    '''
    Creates code from the elements submitted in add form.
    '''
    return '_'.join(('UWOSH',
        session['semCode'],
        add_form.sessionLength.data,
        add_form.subject.data,
        add_form.catalogNumber.data,
        'SEC' + add_form.section.data,
        add_form.classNumber.data))


def update_base_course(baseCourse, baseCourseData, courseDict):
    '''
    Populates baseCourse dictionary with user-selected baseCourse data.
    '''
    baseCourseId = int(baseCourseData)
    for course in courseDict:
        if course['courseId'] == baseCourseId:
            baseCourse.update(course)


app.jinja_env.globals.update(parse_code=parse_code)


if __name__ == '__main__':
    app.run(debug=True)
