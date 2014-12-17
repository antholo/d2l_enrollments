from flask import Flask, render_template, request, session, flash, redirect, url_for, jsonify
from functools import wraps
import requests
import os
#import d2lvalence.auth as d2lauth
import auth2 as d2lauth
import json

# org unit type id for courses in D2L
COURSE_UNIT_TYPE_ID = '3'

# API version
VER = '1.4'

app = Flask(__name__)
app.config.from_pyfile('app_config.cfg')

AUTH_ROUTE = "/token"
AUTH_CB = '{0}://{1}:{2}{3}'.format(app.config['SCHEME'], app.config['HOST'], app.config['PORT'], AUTH_ROUTE)
# 


appContext = d2lauth.fashion_app_context(app_id=app.config['APP_ID'],
                                         app_key=app.config['APP_KEY'])


@app.route('/<semesterCode>')
@app.route('/login/<semesterCode>')
def login(semesterCode):
    '''
    Checks if user context is stored in session and redirects to authorization handler if it is.
    If not, renders login template with link to D2L login and callback route to authorization handler.
    Params:
        SemesterCode - calling app needs to get semesterCode from user and plug into route
    '''
    session['semesterCode'] = semesterCode
    if 'userContext' in session:
        return redirect(url_for('auth_handler'))
    else:
        authUrl = appContext.create_url_for_authentication(
            host=app.config['LMS_HOST'], 
            client_app_url=AUTH_CB,
            encrypt_request=app.config['ENCRYPT_REQUESTS'])
        print(authUrl)
        return render_template('login.html', authUrl=authUrl)


@app.route(AUTH_ROUTE)
def auth_handler():
    '''
    Creates D2L user context for calling API routes and stores it in session. 
    Redirects to enrollment handler--doesn't render a page.
    '''
    print("Request uri", request.url)
    uc = appContext.create_user_context(
        result_uri=request.url, 
        host=app.config['LMS_HOST'],
        encrypt_requests=app.config['ENCRYPT_REQUESTS'])
    print("User Context", uc)
    session['userContext'] = uc.get_context_properties()
    return redirect(url_for('enrollment_handler'))


@app.route('/enrollments')
def enrollment_handler():
    '''
    Builds and sends request to D2L API "myenrollments" route. Sorts through json response for courses in most current semester.
    Build json response containing courses from most current semester.
    '''
    if 'userContext' not in session:
        return redirect(url_for('login'))

    uc = appContext.create_user_context(
            d2l_user_context_props_dict=session['userContext'])

    identifiers = requests.get(uc.create_authenticated_url('/d2l/api/lp/{0}/users/whoami'.format(VER))).json()
    print('IDENTIFIERS', identifiers)    
    print("enrollment_handler: ", uc)
    semesterCode = session['semesterCode'] # test with 0685
    myUrl = uc.create_authenticated_url('/d2l/api/lp/{0}/enrollments/myenrollments/'.format(VER))
    kwargs = {'params': {}}
    kwargs['params'].update({'orgUnitTypeId': COURSE_UNIT_TYPE_ID})
    kwargs['params']['bookmark'] = None
    r = requests.get(myUrl, **kwargs)
    courseList = []
    end = False
    while end == False:
        for course in r.json()['Items']:
            if course['OrgUnit']['Code'][6:10] == semesterCode:
                courseList.append(course)
        if r.json()['PagingInfo']['HasMoreItems'] == True:
            kwargs['params']['bookmark'] = r.json()['PagingInfo']['Bookmark']
            r = requests.get(myUrl, **kwargs)
        else:
            end = True
    return json.dumps({'identifiers': identifiers, 'courseList': courseList})
    #return render_template('enrollments.html', currentCourses=currentCourses)


app.secret_key = os.urandom(24)


if __name__ == '__main__':
    app.run(debug=True)