from app import app
from flask_migrate import Migrate

migrate = Migrate(app, 'db')


if __name__ == '__main__':
    app.run(debug=True, host='192.168.0.102')