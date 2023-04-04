import firebase_admin
import json

import functions_framework
from firebase_admin import firestore, credentials
from flask import Flask, request, jsonify

cred = credentials.Certificate('voter-api-382611-firebase-adminsdk-w75cs-2c06d486af.json')
firebase_admin.initialize_app(cred)

app = Flask(__name__)
database = firestore.client()


@functions_framework.http
def main(request):
    if "students" in request.path:
        if request.method == "GET":
            return get_voter()
        elif request.method == "POST" and "create" in request.path:
            return create_voter()
        elif request.method == "POST" and "update" in request.path:
            return update_voter()
        elif request.method == "DELETE":
            return delete_voter()

    elif "election" in request.path:
        if request.method == "GET":
            return get_election()
        elif request.method == "POST":
            return create_election()
        elif request.method == "DELETE":
            return delete_election()
        elif request.method == "PATCH":
            return vote()
    else:
        return 400


# This function queries a voter's record
@app.route('/students/get_voter', methods=['GET'])
def get_voter():
    student_id = request.get_json()['student_id']
    voter_record = database.collection('students').document(student_id)
    data = voter_record.get()
    voter_data = data.to_dict()
    if len(voter_data) > 0:
        return jsonify(voter_data)
    else:
        return jsonify({'error': 'The voter cannot be found'}), 404


# This function creates a voter
@app.route('/students/create_voter', methods=['POST'])
def create_voter():
    voter_records = request.get_json()

    # Checking if the student already exists in the database
    query = database.collection('students').where('student_id', '==', voter_records['student_id']).get()
    if len(query) > 0:
        return jsonify({'error': 'There is a duplicate Student ID'}), 400

    # adding voter to the database
    database.collection('students').document(voter_records['student_id']).set(voter_records)

    return jsonify({'message': 'Student created successfully!'}), 200


# This function is responsible for updating a voter's record
@app.route('/students/update_voter', methods=['POST'])
def update_voter():
    record = json.loads(request.data)
    voter_id = record['student_id']

    # Retrieving voter record from the database
    voter_info = database.collection('students').document(voter_id)
    voter_doc = voter_info.get()

    # checking if the voter exists
    if voter_doc.exists:
        # Update the voter record with the new data
        voter_data = voter_doc.to_dict()
        voter_data.update(record)
        voter_info.set(voter_data)

        return jsonify({"Success": f"Student data with voter ID {voter_id} has been updated"}), 200

    else:
        return jsonify({'error': 'The voter could not be updated'}), 404


# This function is responsible for deleting a voter from the records
@app.route('/students/delete_voter', methods=['DELETE'])
def delete_voter():
    record = json.loads(request.data)
    voter_id = record['student_id']

    # Retrieving voter record from Firestore
    voter_ref = database.collection('students').document(voter_id)
    voter_doc = voter_ref.get()

    if voter_doc.exists:
        voter_ref.delete()

        return jsonify(''), 204

    else:
        return jsonify({'error': 'The data cannot be found'}), 404


# This function is responsible for querying an election
@app.route('/elections/get_election', methods=['GET'])
def get_election():
    record = json.loads(request.data)
    election_id = request.args.get('election_id')

    if 'election_id' not in record and not election_id:
        return jsonify({'error': 'election ID is missing'}), 400

    query_ref = database.collection('elections')

    if election_id:
        query = query_ref.where('election_id', '==', election_id)
    else:
        query = query_ref.where('election_id', '==', record['election_id'])

    result = query.get()

    if result:
        for doc in result:
            return jsonify(doc.to_dict())
    else:
        return jsonify({'error': 'The data cannot be found'}), 404


# This function is responsible for creating an election
@app.route('/elections/create_election', methods=['POST'])
def create_election():
    record = json.loads(request.data)

    if 'election_id' not in record:
        return jsonify({'error': 'Missing field electionID in JSON data'}), 400
    if 'candidates' not in record:
        return jsonify({'error': 'Missing field candidates in JSON data'}), 400

    collection_ref = database.collection('elections')

    # checking for id existence
    query = collection_ref.where('election_id', '==', record['election_id']).get()
    if len(query) > 0:
        return jsonify({'error': 'Election already exists'}), 400

    # adding record to the database
    collection_ref.document(record['election_id']).set(record)

    return jsonify({"Success": "Election has been created"}), 200


# This function is responsible for deleting an election
@app.route('/elections/delete_election', methods=['DELETE'])
def delete_election():
    record = json.loads(request.data)
    election_id = record['election_id']

    doc_ref = database.collection('elections').document(election_id)
    election_doc = doc_ref.get()

    if election_doc.exists:
        doc_ref.delete()
        return jsonify(''), 204
    else:
        return jsonify({'error': 'Election does not exist'}), 400


# This function is responsible for the voting process
@app.route('/elections/vote', methods=['PATCH'])
def vote():
    record = json.loads(request.data)
    election_id = record['election_id']
    student_id = record['student_id']

    if 'election_id' not in record:
        return jsonify({'error': 'Missing field electionID in JSON data'}), 400
    elif 'student_id' not in record:
        return jsonify({'error': 'Missing field studentID in JSON data'}), 400
    elif 'candidate_id' not in record:
        return jsonify({'error': 'Missing field candidateID in JSON data'}), 400

    election_ref = database.collection('elections').document(election_id)
    student_ref = database.collection('students').document(student_id)

    election_doc = election_ref.get()
    student_doc = student_ref.get()

    if not election_doc.exists or not student_doc.exists:
        return jsonify({'error': 'The student or election does not exist'}), 404

    # Get election data and check if the candidate is valid
    election_data = election_doc.to_dict()
    if record['candidate_id'] not in election_data['candidates']:
        return jsonify({'error': 'A valid candidate was not given'}), 400

    # Check if the student has already voted
    if student_id in election_data.get('students_voted', []):
        return jsonify({'error': 'The student has already voted'}), 400

    # Update election document with new vote and students_voted list
    vote_count = election_data.get('votes', {}).get(record['candidate_id'], 0)
    election_data['votes'] = {record['candidate_id']: vote_count + 1}
    election_data.setdefault('students_voted', []).append(record['student_id'])
    election_ref.set(election_data)

    return jsonify(election_data)


if __name__ == '__main__':
    app.run(debug=True)
