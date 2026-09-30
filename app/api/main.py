from flask import Flask, request, jsonify

app = Flask(__name__)

@app.get('/api/docs')
def docs():
    return jsonify(['pdf1.pdf', 'doc1.doc', 'text1.txt', 'md1.md'])

@app.post('/api/chat')
def chat():
    data = request.get_json()
    question = data['question']
    docs = data['docs']
    # your real logic here
    return jsonify({'answer': f'You asked "{question}" using {len(docs)} docs'})

if __name__ == '__main__':
    app.run(port=5000, debug=True)