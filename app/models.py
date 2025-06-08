from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User:
    __tablename__ = 'users'
    
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class BonsaiImage:
    __tablename__ = 'bonsai_images'
    
    def __init__(self, id, bonsai_id, user_id, filename, original_filename, created_at=None):
        self.id = id
        self.bonsai_id = bonsai_id
        self.user_id = user_id
        self.filename = filename
        self.original_filename = original_filename
        self.created_at = created_at or datetime.utcnow()
    
    def __repr__(self):
        return f'<BonsaiImage {self.id} for bonsai {self.bonsai_id}>'