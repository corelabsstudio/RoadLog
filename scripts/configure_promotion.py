"""Provision existing authorized accounts. Prints booleans/account names only."""
import json
import os
from pathlib import Path
import sys
import urllib.request
from dotenv import dotenv_values
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.promotion import Promotion

ROOT = Path(__file__).resolve().parents[1]
P='9d3da15b-b2e6-4790-af3c-b0229e2d1965'
E='367f2cc2-ac64-4daf-b04d-0d28f4ac97c7'
S='ebf3faf1-2f14-425a-acad-9cc2c67fa633'
token=(ROOT/'.launch/railway.token').read_text(encoding='utf-8-sig').strip().splitlines()[0].strip().strip('"').strip("'")
def gql(query,variables):
    req=urllib.request.Request('https://backboard.railway.app/graphql/v2',data=json.dumps({'query':query,'variables':variables}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=40) as r:body=json.load(r)
    if body.get('errors'):raise RuntimeError('Railway operation rejected')
    return body['data']

v=gql('query($p:String!,$e:String!,$s:String!){variables(projectId:$p,environmentId:$e,serviceId:$s)}',{'p':P,'e':E,'s':S})['variables']
new={}
for account in ('roadlog_saju','mumung_fact'):
    local=dotenv_values(ROOT/'.launch'/('instagram-'+account+'.env'))
    new['PROMO_IG_'+account.upper()+'_TOKEN']=local['INSTAGRAM_ACCESS_TOKEN']
t=dotenv_values(ROOT/'.launch/threads.env')
new['THREADS_ACCESS_TOKEN']=t['THREADS_ACCESS_TOKEN']
new['THREADS_USER_ID']=t['THREADS_USER_ID']
os.environ.update({k:str(val) for k,val in {**v,**new}.items() if val is not None})
service=Promotion(ROOT/'data', ROOT/'web')
print(json.dumps({'configured':service.configured()},ensure_ascii=False))
try:
    print(json.dumps({'verified_accounts':[x['channel'] for x in service.identities()]},ensure_ascii=False))
except ValueError as error:
    print(json.dumps({'account_verification_error':str(error)},ensure_ascii=True))
if '--apply' in sys.argv:
    for name,value in new.items():
        if v.get(name)==value:continue
        gql('mutation($input:VariableUpsertInput!){variableUpsert(input:$input)}',{'input':{'projectId':P,'environmentId':E,'serviceId':S,'name':name,'value':value,'skipDeploys':True}})
    print('account_variables_saved')
else:
    print('read_only_check')
