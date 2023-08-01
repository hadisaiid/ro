from flask import Flask, jsonify, request, send_file
from flask_mysqldb import MySQL
from flask_restful import Resource, Api
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
import os

app = Flask(__name__)
app.secret_key = '123' 
from datetime import timedelta
app.config['JWT_SECRET_KEY'] = '123'

app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7) 
api = Api(app)
jwt = JWTManager(app)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'ro'
app.config['UPLOAD_FOLDER'] = 'app/static/videos'
app.config['UPLOAD_FILES_FOLDER'] = 'app/static/files'


mysql = MySQL(app)

from app import routes


#####################################
#####################################
#####################################
# API
#####################################
#####################################
#####################################

from flask_restful import Resource, Api
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from jwt import ExpiredSignatureError, InvalidTokenError

from app.routes import calculate_user_progress, generate_certificate_data, send_png

class LoginResource(Resource):
    def post(self):
        cursor = mysql.connection.cursor()
        login_data = request.get_json()
        email = login_data.get('email')
        password = login_data.get('password')

        cursor.execute("SELECT * FROM user WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user is not None and user[3] == password:
            access_token = create_access_token(identity=user[0])

            return {'message': 'Login successful', 'access_token': access_token}, 200
        else:
            return {'message': 'Invalid credentials'}, 401

api.add_resource(LoginResource, '/api/login')


class UserProgressResource(Resource):
    @jwt_required()   
    def get(self, course_id):
        try:
            user_id = get_jwt_identity()

            progress = calculate_user_progress(user_id, course_id)

            if progress is not None:
                return {'course_id': course_id, 'progress': progress}, 200
            else:
                return {'message': 'Course progress not found'}, 404
        except ExpiredSignatureError:
            return {'message': 'Token has expired'}, 401
        except InvalidTokenError:
            return {'message': 'Invalid token'}, 401

api.add_resource(UserProgressResource, '/api/progress/<int:course_id>')

def get_enrolled_courses(current_user_id):
    cursor = mysql.connection.cursor()
    query = "SELECT course.* FROM course " \
        "JOIN user_course ON course.id = user_course.course_id " \
        "WHERE user_course.user_id = %s"
    cursor.execute(query, (current_user_id,))
    return cursor.fetchall()

class EnrolledCoursesResource(Resource):
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()
        enrolled_courses = get_enrolled_courses(current_user_id)     # Replace this with your actual data retrieval logic
        return [{'id': course[0], 'title': course[1], 'progress': calculate_user_progress(current_user_id, course[0])} for course in enrolled_courses], 200

api.add_resource(EnrolledCoursesResource, '/api/enrolled_courses')

class DownloadCertificateResource(Resource):
    @jwt_required()
    def get(self, course_id):
        current_user_id = get_jwt_identity()
        
        certificate_file_path = download_certificate(current_user_id, course_id)
        certificate_file_path = "static/" + certificate_file_path
        if certificate_file_path:
            return {"path": certificate_file_path}
        else:
            return {'message': 'Certificate not found'}, 404
api.add_resource(DownloadCertificateResource, '/api/download_certificate/<string:course_id>')


from PIL import Image, ImageDraw, ImageFont

def download_certificate(user_id, course_id):
    certificate_data = generate_certificate_data(user_id, course_id)
    return generate_certificate_png(certificate_data)
   
def generate_certificate_png(certificate_data):
    static_folder = 'app/static'

    logo_img = Image.open('app/static/assets/logo.png')

    logo_position = (50, 50)

    image = Image.new('RGB', (1000, 600), color='white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", size=30)
    image.paste(logo_img, logo_position)

    x, y = 50, 300
    draw.text((x, y), "Certificate of Completion", fill="black", font=font)
    draw.text((x, y + 100), f"Presented to: {certificate_data['full_name']}", fill="black", font=font)
    draw.text((x, y + 200), f"For successfully completing the course: {certificate_data['course_title']}", fill="black", font=font)
    draw.text((x, y + 300), f"Completion Date: {certificate_data['completion_date']}", fill="black", font=font)

    certificate_filename = f"{certificate_data['full_name']}_certificate.png"
    certificate_path = os.path.join(static_folder, certificate_filename)
    image.save(certificate_path)

    return certificate_filename