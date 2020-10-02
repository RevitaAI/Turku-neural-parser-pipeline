import os
import flask
from flask import Response, request
import sys
import requests
import multiprocessing

app=flask.Flask(__name__)
clusters_port = "7689"
cluster_size = 2
cluster_nodes = [
    'turku-neural-parser-pipeline_turku_parser_' + str(_)
    for _ in range(1, cluster_size + 1)
]

def dispatch(input_tup):
    try:
        payload, url, port = input_tup
        headers = { 'Content-Type': 'text/plain; charset=utf-8' }
        response = requests.request("POST", 'http://{}:{}'.format(url, port), 
        headers=headers, data = payload, timeout=10)
        return response.text
    except Exception as e:
        print(e)
        return ''

def parallel_run(text):
    p = multiprocessing.Pool(cluster_size)
    # this needs to be declared global to mutate
    # the resultsAr defined in the enclosing scope
    input_tup = [(text, cluster_node, clusters_port) for cluster_node in cluster_nodes]
    result = p.map(dispatch, input_tup, chunksize=1)
    p.close()
    p.join()
    return result

@app.route("/",methods=["post"])
def parse_get():
    txt=request.get_data(as_text=True)
    result = parallel_run(txt)
    output = '\n'.join(result)
    print(txt, result)
    return Response(output,mimetype="text/plain; charset=utf-8")

if __name__=="__main__":
    app.run(host='0.0.0.0',port='5000')
