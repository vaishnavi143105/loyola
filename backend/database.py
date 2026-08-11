import mysql.connector


def get_connection():

    try:

        connection = mysql.connector.connect(
            host="127.0.0.1",
            port=3306,
            user="root",
            password="2007",
            database="missvoice",
            auth_plugin="mysql_native_password"
        )

        print("MySQL Connected Successfully!")

        return connection

    except mysql.connector.Error as error:

        print("Database Connection Error:", error)

        return None