import os
import flask
from flask import Response, request, jsonify
import sys
import requests
import multiprocessing
import socket

hostname = socket.gethostname()
ip_address = socket.gethostbyname(hostname)

app=flask.Flask(__name__)
clusters_port = "7689"
cluster_size = int(ip_address.split('.')[-1]) - 2 #2
cluster_nodes = [
    'turku-neural-parser-pipeline_turku_parser_' + str(_)
    for _ in range(1, cluster_size + 1)
]


def to_dict(analyzed_sents: str):
    sents = []
    for token in analyzed_sents.split('\n'):
        if not len(sents) or not len(token):
            sents.append({'tokens': [], 'size': 0})
            continue
        if token.startswith('#'):
            if token.startswith('# sent_id'):
                sents[-1]['sent_id'] = int(token.strip('# sent_id = '))
            elif token.startswith('# text'):
                sents[-1]['text'] = token.strip('# text = ')
            continue
        temp = token.split('\t')
        idx, surface, base, pos = temp[:4]
        sents[-1]['tokens'].append({
            'id': int(idx),
            'surface': surface,
            'base': base,
            'pos': pos
        })
        sents[-1]['size'] += 1
    return [_ for _ in sents if _['size']]


def dispatch(input_tup):
    try:
        payload, url, port = input_tup
        headers = { 'Content-Type': 'text/plain; charset=utf-8' }
        response = requests.request("POST", 'http://{}:{}'.format(url, port), 
        headers=headers, data = payload, timeout=10)
        ret = to_dict(response.text)
        return ret
    except Exception as e:
        print(e)
        return ''

def join_result(results: list):
    joined_sents = []
    for sent_list in zip(*results):
        sent = {'text': sent_list[0]['text'], 'sent_id': sent_list[0]['sent_id'], 'tokens': []}
        if any([_['size'] != sent_list[0]['size'] for _ in sent_list]):
            sent['error'] = 'tokenizing error'
            joined_sents.append(sent)
        else:
            token_lists = [_['tokens'] for _ in sent_list]
            is_valid = True
            for token_list in zip(*token_lists):
                if any([_['surface']!=token_list[0]['surface'] for _ in token_list]):
                    is_valid = False
                if is_valid:
                    base_pos_list = [(_['base'], _['pos']) for _ in token_list]
                    base_pos = []
                    for base, pos in set(base_pos_list):
                        conf = sum([_ == (base, pos) for _ in base_pos_list]) / len(base_pos_list)
                        base_pos.append({
                            'base': base,
                            'pos': pos,
                            'conf': conf
                        })
                    token = {
                        'id': token_list[0]['id'], 
                        'surface': token_list[0]['surface'], 
                        'base_pos': base_pos
                    }
                    sent['tokens'].append(token)
            if not is_valid:
                sent['tokens'] = []
                sent['error'] = 'tokenizing error'
        joined_sents.append(sent)
    return joined_sents


def parallel_run(text):
    p = multiprocessing.Pool(cluster_size)
    # this needs to be declared global to mutate
    # the resultsAr defined in the enclosing scope
    input_tup = [(text, cluster_node, clusters_port) for cluster_node in cluster_nodes]
    result = p.map(dispatch, input_tup, chunksize=1)
    p.close()
    p.join()
    return join_result(result)

@app.route("/",methods=["post"])
def parse_get():
    txt=request.get_data(as_text=True)
    result = parallel_run(txt)
    return jsonify(result)

if __name__=="__main__":
    app.run(host='0.0.0.0',port='5000')
