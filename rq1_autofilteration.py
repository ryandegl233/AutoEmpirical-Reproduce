# %%
import requests
import time
import os
import json
import pickle
from tqdm import tqdm,trange
from openai import OpenAI
import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv()
YUNWU_BASE_URL = "https://yunwu.ai/v1"
os.environ.setdefault("OPENAI_BASE_URL", YUNWU_BASE_URL)

#load prompts from data/prompts.yaml
import yaml
with open('data/prompts.yaml', 'r') as file:
    prompts = yaml.safe_load(file)

#load CollectedIssues.csv
df = pd.read_csv('./data/sampled_issues_dataset.csv')

def Query(model, sys, usr, max_retries=3, retry_delay=10):
    client = OpenAI(
        api_key=os.getenv("YUNWU_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("YUNWU_BASE_URL") or os.getenv("OPENAI_BASE_URL", YUNWU_BASE_URL),
    )
    for i in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys},
                    {"role": "user", "content": usr},
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            print(e)
            time.sleep(retry_delay)
            continue
    return None

# Representative mainstream chat models for RQ1 autofilteration.
model_list = ["gpt-5.5", "deepseek-v4-pro", "qwen3-235b-a22b","claude-opus-4-7"]

for model in model_list:
    results = []
    for idx, row in tqdm(df.iterrows(), total=len(df)):
    # for idx, row in tqdm(df.head(50).iterrows(), total=50):
        url = str(row['issue'])
        if 'issue' not in url:
            continue

        title = str(row.get('title', ''))
        state = str(row.get('state', ''))
        created_at = str(row.get('created_at', ''))
        body = str(row.get('body', ''))
        comments_content = str(row.get('comments_content', ''))

        issue_report = f"##Issue Report\n###[Title]: {title}\n###[State]: {state}\n###[Created At]: {created_at}\n###[Body]:\n {body}\n###[Other Comments]:\n {comments_content}"

        user_prompt = prompts['user_input']['template'].replace("{{ISSUE REPORT}}", issue_report)
        sys_prompt = prompts['sys_filteration']['template']

        response = Query(model, sys_prompt, user_prompt)

        # copy row, and append a new column 'LLM_classification' with the response
        new_row = row.copy()
        new_row['LLM_classification'] = response
        results.append(new_row)

        # save results to a new csv file
        pd.DataFrame(results).to_csv(f'./res/Filteration_{model}.csv', index=False)
        # break
