# Python-work
This repo will contain my python related development and POCS

# MyFirstApi - Contact Book & Todo Manager

A robust RESTful API built with **Flask** and **MySQL** that allows users to manage contacts and todo lists simultaneously. This project features automatic database schema synchronization using **SQLAlchemy** and interactive documentation via **Flask-Smorest (Swagger UI)**.

## 🚀 Features
* **Dual-Table Integration**: Manages two separate tables (`contacts` and `todos`) within a single MySQL database.
* **Automated Documentation**: Interactive API testing available at `/swagger`.
* **Environment Security**: Uses `.env` for secure database credential management.
* **CRUD Operations**: Full Create, Read, Update, and Delete support for both modules.

## 🛠️ Tech Stack
* **Language**: Python 3.x
* **Framework**: Flask / Flask-Smorest
* **Database**: MySQL
* **ORM**: SQLAlchemy
* **Documentation**: OpenAPI (Swagger UI)

## 📋 Prerequisites
* MySQL Server installed and running.
* Python 3.x and `pip`.

## ⚙️ Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <your-repo-link>
   cd MyFirstApi

2. Set up Environment Variables: Create a .env file in the root directory and add your MySQL credentials:
    DB_USER=root
    DB_PASSWORD=your_password
    DB_HOST=localhost
    DB_PORT=3306
    DB_NAME=my_first_Api_db

3. Install Dependencies:
    pip install -r requirements.txt

4. Initialize the Database: Run this command to create the tables automatically:
    python -c "from app import create_app; from app.database import db; app=create_app(); app.app_context().push(); db.create_all()"

5. Run the Application:
    python run.py

🧪 Testing the API
     Open your browser and navigate to: http://127.0.0.1:5000/swagger
