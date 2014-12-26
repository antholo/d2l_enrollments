# enrollments/views.py

from flask import Flask, render_template, request, session, flash, redirect, url_for
from flask_mail import Mail, Message
from functools import wraps
from form import SelectSemesterForm, SelectCoursesForm, AdditionalCourseForm
import requests
import os
import auth2 as d2lauth


app = Flask(__name__)
app.config.from_pyfile('app_config.cfg')
mail = Mail(app)
app.secret_key = os.urandom(24)

appContext = d2lauth.fashion_app_context(app_id=app.config['APP_ID'],
                                         app_key=app.config['APP_KEY'])


def login_required(test):
    @wraps(test)
    def wrap(*args, **kwargs):
        if 'userContext' in session:
            return test(*args, **kwargs)
        else:
            flash('You need to login first.')
            return redirect(url_for('login'))
    return wrap


@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(app.config['REDIRECT_AFTER_LOGOUT'])


@app.route('/')
@app.route('/login')
def login():
    '''
    Checks if user context is stored in session and redirects to authorization handler if it is.
    If not, renders login template with link to D2L login and callback route to authorization handler.
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
    uc = appContext.create_user_context(
        result_uri=request.url, 
        host=app.config['LMS_HOST'],
        encrypt_requests=app.config['ENCRYPT_REQUESTS'])
    my_url = uc.create_authenticated_url('/d2l/api/lp/{0}/users/whoami'.format(app.config['VER']))
    r = requests.get(my_url)

    #print('WHOAMI', r.json())

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
    error = None
    form = SelectSemesterForm(request.form)
    if 'semCode' in session:
        session.pop('semCode')
    if 'coursesToCombine' in session:
        session.pop('coursesToCombine')
    if request.method == 'POST':
        if form.is_submitted():
            semCode = get_semester(form.semester.data, form.year.data)
            session['semCode'] = semCode

            try:
                courseDict = session['courseDict'][semCode]
            except KeyError:
                error = "No courses are listed with you enrolled as an instructor for that semester."
                return render_template("semester.html", form=form, error=error)
        return redirect(url_for('enrollment_handler'))
    else:
        return render_template("semester.html", form=form, error=error)



@app.route('/enrollments', methods=['GET', 'POST'])
@login_required
def enrollment_handler():

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
            courseIds = form.courseIds.data
            coursesToCombine = [course for course in courseDict if course['courseId'] in courseIds]
            baseCourse = {}
            baseCourseId =  int(form.baseCourse.data)
            for course in courseDict:
                if course['courseId'] == baseCourseId:
                    baseCourse.update(course)
            session['baseCourse'] = baseCourse
            if len(coursesToCombine) < 2:
                if request.form['btn'] == 'Add Class':
                    code = '_'.join(('UWOSH',
                        session['semCode'],
                        add_form.sessionLength.data,
                        add_form.subject.data,
                        add_form.catalogNumber.data,
                        'SEC' + add_form.section.data,
                        add_form.classNumber.data))
                    courseToAdd = get_course(uc, code)
                    session['courseDict'][session['semCode']] = update_course_dict(courseDict,
                        courseToAdd['Identifier'],
                        courseToAdd['Name'],
                        code)
                    return redirect(url_for('enrollment_handler'))

                else:    
                    error = 'You must select at least two courses to combine.'
                    return render_template("enrollments.html", form=form, add_form=add_form, error=error)
                
            else:
                session['coursesToCombine'] = coursesToCombine
                if baseCourse not in coursesToCombine:
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
    msg = Message(subject='Course Combine Confirmation',
        recipients=[app.config['MAIL_DEFAULT_SENDER'], session['uniqueName'] + app.config['EMAIL_DOMAIN']])
    msg.body = generate_msg_text(session['firstName'], session['lastName'], session['coursesToCombine'], session['baseCourse'])
    msg.html = generate_msg_html(session['firstName'], session['lastName'], session['coursesToCombine'], session['baseCourse'])
    mail.send(msg)
    return render_template("confirmation.html", coursesToCombine=session['coursesToCombine'], baseCourse=session['baseCourse'])


def generate_msg_text(firstName, lastName, coursesToCombine, baseCourse):
    opening ="Hello {0} {1},\nYou have asked to have the following courses combined into {2}, {3}:\n\nCourse Name\t(Course Id)\n".format(firstName, lastName, baseCourse['parsed'], baseCourse['name'])
    courseTable = "\n".join("{!s}\t({!s})".format(course['name'], course['code']) for course in coursesToCombine)
    closing = "\nIf this is incorrect, please contact our D2L site administrator at " + app.config['EMAIL_SITE_ADMIN'] + "."
    msg_body = opening + courseTable + closing
    return msg_body


def generate_msg_html(firstName, lastName, coursesToCombine, baseCourse):
    opening ="<p>Hello {0} {1},</p><p>You have asked to have the following courses combined into {2}, {3}:</p>".format(firstName, lastName, baseCourse['parsed'], baseCourse['name'])
    tableHead = "<table><thead><tr><th>Course Name</th><th>(Course Id)</th></thead>"
    courseTable = "".join("<tr><td>{!s}</td><td>({!s})</td></tr>".format(course['name'], course['code']) for course in coursesToCombine)
    tableClose = "</table>"
    closing = "<p>If this is incorrect, please contact our D2L site administrator at " + app.config['EMAIL_SITE_ADMIN'] + ".</p>"
    msg_html = opening + tableHead + courseTable + tableClose + closing
    return msg_html

def get_semester(semester, year):
    '''
    Determines semester code for UWO courses.
    '''
    if semester == 'Fall':
        precedingDigits = year
        finalDigit = '0'
    if semester == 'Spring':
        precedingDigits = str(int(year) - 1)
        finalDigit = '5'
    if semester == 'Summer':
        precedingDigits = str(int(year) - 1)
        finalDigit = '8'
    semesterCode = precedingDigits + finalDigit
    if len(semesterCode) < 4:
        semesterCode = '0' + semesterCode
    return semesterCode


def get_courses(uc):
    '''
    Creates dictionary of lists of courses keyed by semester code and stores 
    it in session for easy access post-creation.
    '''
    myUrl = uc.create_authenticated_url('/d2l/api/lp/{0}/enrollments/users/{1}/orgUnits/'.format(app.config['VER'], session['userId']))
    kwargs = {'params': {}}
    kwargs['params'].update({'roleId':app.config['ROLE_ID']})
    kwargs['params'].update({'orgUnitTypeId': app.config['ORG_UNIT_TYPE_ID']})
    r = requests.get(myUrl, **kwargs)

    #print(r.json()['Items'])

    courseDict = {}
    end = False
    while end == False:
        for course in r.json()['Items']:
            semCode = str(course['OrgUnit']['Code'][6:10])
            if semCode.isdigit():
                if semCode not in courseDict:
                    courseDict[semCode] = []
                #courseDict[semCode].append({'courseId': course['OrgUnit']['Id'], 'name': course['OrgUnit']['Name']})
                """courseDict[semCode].append({'courseId': course['OrgUnit']['Id'],
                    'name': course['OrgUnit']['Name'],
                    'code': course['OrgUnit']['Code'],
                    'parsed': parse_code(course['OrgUnit']['Code'])})"""
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
    courseDict.append({u'courseId': int(courseId), u'name': name, u'code': code, u'parsed': parse_code(code)})
    return courseDict

def get_course(uc, code):
    myUrl = uc.create_authenticated_url('/d2l/api/lp/{0}/orgstructure/'.format(app.config['VER']))
    kwargs = {'params': {}}
    kwargs['params'].update({'orgUnitCode': code})
    kwargs['params'].update({'orgUnitType': app.config['ORG_UNIT_TYPE_ID']})
    r = requests.get(myUrl, **kwargs)
    return r.json()['Items'][0]

def add_course(courseId):
    myUrl = uc.create_authenticated_url('/d2l/api/lp/{0}/orgstructure/{1}'.format(app.config['VER'], courseId))
    r = requests.get(myUrl, **kwargs)
    if r.json():
        response = r.json()
        #print r.json()
        courseInfo = {'courseId': courseId,
            'name': response['Name'],
            'code': response['Code'],
            'parsed': parse_code(response['Code'])}
        return courseInfo
    else:
        print r.reason()

def parse_code(code):
    parsed = code.split("_")
    return parsed[3] + " " + parsed[4] + " " + parsed[5]


def get_courseId_choices(courseDict):
    return [(course['courseId'], 
        course['name'] + ", " + course['parsed']) for course in courseDict]


def get_baseCourse_choices(courseDict):
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


app.jinja_env.globals.update(parse_code=parse_code)


if __name__ == '__main__':
    app.run(debug=True)
