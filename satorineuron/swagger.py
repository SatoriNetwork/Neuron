from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import requests

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://chalory:12345678@localhost/satori'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize Swagger documentation with Flask-RESTX
api = Api(app, version='1.0', title='Proposal API',
    description='API for managing proposals and votes.')

# Define database models
class ProposalModel(db.Model):
    __tablename__ = 'proposals'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    proposal_date = db.Column(db.DateTime(timezone=True), nullable=False)
    complete_date = db.Column(db.DateTime(timezone=True))
    value = db.Column(db.Numeric(15, 2), nullable=False)
    image_url = db.Column(db.Text)

class VoteModel(db.Model):
    __tablename__ = 'votes'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id = db.Column(UUID(as_uuid=True), db.ForeignKey('proposals.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), nullable=False)
    vote = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('proposal_id', 'user_id', name='uq_proposal_user'),)

# Define Swagger models
proposal_model = api.model('Proposal', {
    'id': fields.String(description='The unique identifier for the proposal'),
    'title': fields.String(required=True, description='The title of the proposal'),
    'description': fields.String(required=True, description='A detailed description of the proposal'),
    'proposal_date': fields.DateTime(required=True, description='The date when the proposal was submitted'),
    'complete_date': fields.DateTime(description='The date when the proposal was completed or closed'),
    'value': fields.Float(required=True, description='The monetary value or cost associated with the proposal'),
    'image_url': fields.String(description='URL to an image related to the proposal'),
    'yes_votes': fields.Integer(description='The number of yes votes for this proposal'),
    'no_votes': fields.Integer(description='The number of no votes for this proposal')
})

vote_model = api.model('Vote', {
    'proposal_id': fields.String(required=True, description='The unique identifier of the proposal being voted on'),
    'user_id': fields.String(required=True, description='The unique identifier of the user casting the vote'),
    'vote': fields.Boolean(required=True, description='The vote: True for Yes, False for No')
})

# Define API routes
@api.route('/proposals')
class ProposalList(Resource):
    @api.doc('list_proposals', 
             description='Retrieves a list of all proposals with their vote counts.',
             responses={
                 200: 'Success',
                 500: 'Internal Server Error'
             })
    @api.marshal_list_with(proposal_model)
    def get(self):
        """
        List all proposals
        Returns a list of all proposals, including their titles, descriptions, dates, and vote counts.
        """
        proposals = ProposalModel.query.all()
        result = []
        for proposal in proposals:
            proposal_data = {
                'id': str(proposal.id),
                'title': proposal.title,
                'description': proposal.description,
                'proposal_date': proposal.proposal_date,
                'complete_date': proposal.complete_date,
                'value': float(proposal.value),
                'image_url': proposal.image_url,
                'yes_votes': VoteModel.query.filter_by(proposal_id=proposal.id, vote=True).count(),
                'no_votes': VoteModel.query.filter_by(proposal_id=proposal.id, vote=False).count()
            }
            result.append(proposal_data)
        return result

@api.route('/votes')
class VoteSubmission(Resource):
    @api.doc('submit_vote', 
             description='Submit a vote for a specific proposal.',
             responses={
                 200: 'Vote submitted successfully',
                 400: 'Invalid vote submission',
                 500: 'Internal Server Error'
             })
    @api.expect(vote_model)
    @api.response(200, 'Vote submitted successfully')
    @api.response(400, 'Invalid vote submission')
    def post(self):
        """
        Submit a vote for a proposal
        Accepts a vote (yes/no) for a specific proposal from a user. Each user can only vote once per proposal.
        """
        data = request.json
        new_vote = VoteModel(
            proposal_id=uuid.UUID(data['proposal_id']),
            user_id=uuid.UUID(data['user_id']),
            vote=data['vote']
        )
        db.session.add(new_vote)
        try:
            db.session.commit()
            return {"message": "Vote submitted successfully"}, 200
        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 400

# Separate functions to call the endpoints
def getProposals():
    """
    Function to get all proposals by calling the API endpoint.
    """
    try:
        response = requests.get('http://localhost:5000/proposals')
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to get proposals. Status code: {response.status_code}")
            return []
    except requests.RequestException as e:
        print(f"Error occurred while fetching proposals: {str(e)}")
        return []

def submitVote(proposal_id, user_id, vote):
    """
    Function to submit a vote by calling the API endpoint.
    """
    try:
        data = {
            "proposal_id": str(proposal_id),
            "user_id": str(user_id),
            "vote": vote
        }
        response = requests.post('http://localhost:5000/votes', json=data)
        if response.status_code == 200:
            return True, "Vote submitted successfully"
        else:
            return False, f"Failed to submit vote. Status code: {response.status_code}"
    except requests.RequestException as e:
        return False, f"Error occurred while submitting vote: {str(e)}"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

# Example usage of the separate functions:
# proposals = getProposals()
# for proposal in proposals:
#     print(f"Proposal: {proposal['title']}, Yes votes: {proposal['yes_votes']}, No votes: {proposal['no_votes']}")

# success, message = submitVote(uuid.uuid4(), uuid.uuid4(), True)
# print(message)