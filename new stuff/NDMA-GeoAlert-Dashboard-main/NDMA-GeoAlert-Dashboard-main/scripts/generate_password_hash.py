from werkzeug.security import generate_password_hash

password = input("Enter password: ")

print("Password Hash:")
print(generate_password_hash(password))
