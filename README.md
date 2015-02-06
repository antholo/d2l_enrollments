# D2L Course Combine Request Tool
This helps resolve a problem in instructor requests to the Desire2Learn site administrator for multiple of their courses to be combined. The current form for such requests require instructors to manually enter information, which results in a sometimes bumpy process requiring multiple email or phone call follow-ups. This tools gets information from the instructor and from Desire2Learn, presenting them with a slate of choices of courses to combine. When they confirm their selections, the necessary information is emailed to the D2L site administrator.

## How It Works
Using the authorization code provided by D2L's Valence API, the app first authenticates the user against the site  installation, collecting user tokens and data. Utilizing a service account, the app then requests enrollments for the authenticated user, restricted by the course offering type and instructor role--otherwise, the user could be overwhelmed with their other organizational enrollments, including at organizational and department levels, and courses in which they are enrolled as observers, students, etc.

The user is directed to select a semester, and then is taken to a form listing their enrollments for the selected semester. The semester selection makes use of the four-digit codes for semester, which are included in the response from the call to enrollments, to group courses matching the user's criteria.

The form asks the user to check boxes next to courses needing to be combined, and to select which course will be the base course. On some occasions, instructors have begun developing one of their courses before combining, and it is important that they select the developed course as the base course to which the other(s) will be added.

There are times when instructors might want to combine their course with another in which they are not the instructor, like when co-teaching cross-listed sections. To accomodate such requests, there is an additional form in which they can provide course code details from PeopleSoft. A link to TitanWeb and an image detailing the locations of the relevant information are included in the form. Once an instructor submits this form, and the data is valid, the course appears in the list of courses they can request combined. 

When the instructor confirms that their request is accurate, two emails are generated and sent. One is a confirmation email for the instructor and the other goes to the D2L site administrator. The email includes the course code for easily locating the course in D2L, and the site administrator reviews the request and makes the combination.

## Configuration
A configuration file named app_config.cfg is needed for this app to run properly. As it contains some sensitive information, it is not included in this repository. A template is provided below:

```
# app_config.cfg

# cross-site request forgery turned on - secret key generated in views.py
WTF_CSRF_ENABLED = True

# app id/key pair strings from D2L
# Keys can be requested or recovered at https://keytool.valence.desire2learn.com/Auth/LogOn?ReturnUrl=%2f
APP_ID = ''
APP_KEY = ''

# service account ID and Key
# The API test tool can help gather this information - https://apitesttool.desire2learnvalence.com/
USER_ID = ''
USER_KEY = ''

HOST = 'localhost'
PORT = '5000'
SCHEME = 'HTTP'
# LMS host is address of D2L installation.
LMS_HOST = ''
LMS_PORT = '443'
ENCRYPT_REQUESTS = True
VERIFY = False
# LMS versions for learning platform, learning environment, and eportfolio
LMS_VER = {'lp':1.3,'le':10.3,'ep':2.3}

# API version
VER = '1.4'

# authorization route
AUTH_ROUTE = "/token"

# authorization callback route
AUTH_CB = '{0}://{1}:{2}{3}'.format(SCHEME, HOST, PORT, AUTH_ROUTE)

# Constants for API calls
# org unit type id for courses in D2L
COURSE_UNIT_TYPE_ID = '3'

# code for course in orgunits API route call
ORG_UNIT_TYPE_ID = '3'

# code for instructor role in orgunits call
ROLE_ID = '914'

# constants for semester code function in views.py
FALL = '0'
SPRING = '5'
SUMMER = '8'

# email settings
MAIL_SERVER = ''
MAIL_PORT = 465
MAIL_USE_SSL = True
MAIL_DEFAULT_SENDER = ''
MAIL_USERNAME = ''
MAIL_PASSWORD = ''
EMAIL_DOMAIN = ''

# email address of the site administrator to receive combine requests
EMAIL_SITE_ADMIN = ''

# redirect url following logout
REDIRECT_AFTER_LOGOUT = ""
```
