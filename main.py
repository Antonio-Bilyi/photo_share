from fastapi import FastAPI

from app.routes import users, photos, comments


app = FastAPI()


app.include_router(users.router, prefix='/api')
app.include_router(photos.router, prefix='/api')
app.include_router(comments.router, prefix='/api')

@app.get('/')
def greeting():
    return {'message': 'Welcome to Photo Share!'}