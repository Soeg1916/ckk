from app import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True)
    username = db.Column(db.String(64))
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username or self.telegram_id}>'

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    character_id = db.Column(db.String(64), nullable=False)
    total_messages = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to user
    user = db.relationship('User', backref=db.backref('conversations', lazy=True))
    
    def __repr__(self):
        return f'<Conversation {self.user_id}:{self.character_id}>'

class ConversationMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to conversation
    conversation = db.relationship('Conversation', backref=db.backref('messages', lazy=True))
    
    def __repr__(self):
        return f'<Message {self.conversation_id}:{self.role}>'

class CharacterStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    character_id = db.Column(db.String(64), nullable=False)
    mood = db.Column(db.Float, default=5.0)
    conversation_count = db.Column(db.Integer, default=0)
    last_interaction = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Store personality stats as JSON
    personality_json = db.Column(db.Text)
    
    # Relationship to user
    user = db.relationship('User', backref=db.backref('character_stats', lazy=True))
    
    def __repr__(self):
        return f'<CharacterStat {self.user_id}:{self.character_id}>'