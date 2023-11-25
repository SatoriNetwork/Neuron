# we should use pydantic for apis
#
# from pydantic import BaseModel, validator
#
# class User(BaseModel):
#    name: str
#    age: int
#
#    @validator('age')
#    def check_age(cls, value):
#        if value < 18:
#            raise ValueError('Age must be at least 18')
#        return value
