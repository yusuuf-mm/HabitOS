import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

hash_val = "$2b$12$/9KtPdGeNPEb41wxdR1kZ.gjBUplwdBvsDawDyv3aSeoaYPmGpWwa"
password = "Password123!"

print(f"Verifying '{password}' against '{hash_val}'")
print(f"Result: {verify_password(password, hash_val)}")
