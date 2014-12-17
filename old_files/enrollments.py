from flask import Flask, render_template, request, session, flash, redirect, url_for, g
from functools import wraps
import requests
import os
import d2lvalence.auth as d2lauth

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


@app.route('/')#, methods=['GET', 'POST'])
@app.route('/login')
def login():
    if 'userContext' in session:
        return redirect(url_for(AUTH_ROUTE))
    else:
        authUrl = appContext.create_url_for_authentication(
            host=app.config['LMS_HOST'], 
            client_app_url=AUTH_CB,
            encrypt_request=app.config['ENCRYPT_REQUESTS'])
        print(authUrl)
        return render_template('login.html', authUrl=authUrl)


@app.route(AUTH_ROUTE)#, method='GET')
def auth_handler():
    print(request.url)
    uc = appContext.create_user_context(
        result_uri=request.url, 
        host=app.config['LMS_HOST'],
        encrypt_requests=app.config['ENCRYPT_REQUESTS'])
    
    session['userContext'] = uc.get_context_properties()
    print("auth_handler: ", session)
    return redirect(url_for('enrollment_handler'))


@app.route('/enrollments')#, methods=['GET', 'POST'])
def enrollment_handler():
    if 'userContext' not in session:
        print("Hey, where's the userContext?")
        return redirect(url_for('login'))

    uc = appContext.create_user_context(
            d2l_user_context_props_dict=session['userContext'])
    print("enrollment_handler: ", uc)
    myUrl = uc.create_authenticated_url('/d2l/api/lp/{0}/enrollments/myenrollments/'.format(VER))
    kwargs = {'params': {}}
    kwargs['params'].update({'orgUnitTypeId': COURSE_UNIT_TYPE_ID})
    kwargs['params']['bookmark'] = None
    r = requests.get(myUrl, **kwargs)
    print(r)
    courseList = r.json()['Items']
    #print("Type: ", type(courseList))
    while r.json()['PagingInfo']['HasMoreItems']:
        kwargs['params']['bookmark'] = r.json()['PagingInfo']['Bookmark']
        r = requests.get(myUrl, **kwargs)
        print(r)
        courseList.append(r.json()['Items'])
    startDate = courseList[-1]['Access']['StartDate']
    currentCourses = []
    for course in courseList:
        if course['Access']['StartDate'] == startDate:
            currentCourses.append(course)
    print(currentCourses)
    return render_template('enrollments.html', currentCourses=currentCourses)


app.secret_key = os.urandom(24)


if __name__ == '__main__':
    app.run(debug=True)