# enrollments/views.py

from flask import Flask, render_template, request, session, flash, redirect, url_for
from flask_mail import Mail, Message
from functools import wraps
from form import SelectSemesterForm, SelectCoursesForm
import requests
import os
#import d2lvalence.auth as d2lauth
import auth2 as d2lauth


app = Flask(__name__)
app.config.from_pyfile('app_config.cfg')
mail = Mail(app)

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


@app.route('/')#, methods=['GET', 'POST'])
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
        #print(authUrl)
        return render_template('login.html', authUrl=authUrl)


@app.route(app.config['AUTH_ROUTE'])#, method='GET')
def auth_handler():
    #print("Request uri", request.url)
    uc = appContext.create_user_context(
        result_uri=request.url, 
        host=app.config['LMS_HOST'],
        encrypt_requests=app.config['ENCRYPT_REQUESTS'])
    #print("User Context", uc)
    # call whoami and store user info
    my_url = uc.create_authenticated_url('/d2l/api/lp/{0}/users/whoami'.format(app.config['VER']))
    r = requests.get(my_url)
    print('WHOAMI', r.json())
    session['firstName'] = r.json()['FirstName']
    session['lastName'] = r.json()['LastName']
    session['userId'] = r.json()['Identifier']
    #session['uniqueName'] = r.json()['UniqueName']
    session['uniqueName'] = 'lookerb'

    # feed in service account ID and key and store user context
    uc.user_id = app.config['USER_ID']
    uc.user_key = app.config['USER_KEY']
    session['userContext'] = uc.get_context_properties()
    return redirect(url_for('select_semester'))


@app.route('/semester/', methods=['GET', 'POST'])
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
            #semCode = get_semester(request.form['semester'], request.form['year'])
            semCode = get_semester(form.semester.data, form.year.data)
            session['semCode'] = semCode
        return redirect(url_for('enrollment_handler'))
    else:
        return render_template("semester.html", form=form, error=error)



@app.route('/enrollments', methods=['GET', 'POST'])
@login_required
def enrollment_handler():
    '''if 'userContext' not in session:
        print("Hey, where's the userContext?")
        return redirect(url_for('login'))'''

    uc = appContext.create_user_context(
            d2l_user_context_props_dict=session['userContext'])
    if 'courseDict' not in session:
        session['courseDict'] = get_courses(uc)

    courseDict = session['courseDict'][session['semCode']]
    error = None
    form = SelectCoursesForm(request.form)
    form.courseIds.choices = [(course['courseId'], course['name']) for course in courseDict]
    if request.method == 'POST':
        if form.is_submitted():
            courseIds = form.courseIds.data
            coursesToCombine = [course for course in courseDict if course['courseId'] in courseIds]

            print("COURSE DICT", courseDict)
            print("COURSE IDS", courseIds)
            print("COMBINE", coursesToCombine)
            
            if len(coursesToCombine) < 2:
                error = 'You must select at least two courses to combine.'
                return render_template("enrollments.html", form=form, error=error)
            else:
                session['coursesToCombine'] = coursesToCombine
                return redirect(url_for('confirm_selections'))
        else:
            error = 'The form must be invalid for some reason...'
            return render_template("enrollments.html", form=form, error=error)
    else:
        return render_template("enrollments.html", form=form)


@app.route('/confirmation')
@login_required
def confirm_selections():
    msg = Message(subject='Course Combine Confirmation',
        recipients=['eportfolio@uwosh.edu', session['uniqueName'] + '@uwosh.edu'])
    opening ="Hello {0} {1},\nYour request to combine the following courses:\nCourse Name (Course Id)\n".format(session['firstName'], session['lastName'])
    courseTable = "\n".join("{!s} ({!s})".format(course['name'], course['courseId']) for course in session['coursesToCombine'])
    closing = "If this is incorrect, please contact our D2L site administrator at d2l@uwosh.edu."
    closingHTML = '''
        <p>If this is incorrect, please contact our <a href="mailto:d2l@uwosh.edu">D2L site administrator.'''
    msg.body = opening + courseTable + closing
    mail.send(msg)
    return render_template("confirmation.html", coursesToCombine=session['coursesToCombine'])


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
    courseDict = {}
    end = False
    while end == False:
        for course in r.json()['Items']:
            semCode = str(course['OrgUnit']['Code'][6:10])
            if semCode.isdigit():
                if semCode not in courseDict:
                    courseDict[semCode] = []
                courseDict[semCode].append({'courseId': course['OrgUnit']['Id'], 'name': course['OrgUnit']['Name']})
            if r.json()['PagingInfo']['HasMoreItems'] == True:
                kwargs['params']['bookmark'] = r.json()['PagingInfo']['Bookmark']
                r = requests.get(my_url, **kwargs)
        else:
            end = True
    return courseDict


app.secret_key = os.urandom(24)


if __name__ == '__main__':
    app.run(debug=True)