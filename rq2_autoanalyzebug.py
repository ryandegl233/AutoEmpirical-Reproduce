# %%
import requests
import time
import os
import json
import pickle
from tqdm import tqdm,trange
from openai import OpenAI
import pandas as pd
from typing import List, Tuple
from anthropic import Anthropic
os.environ.setdefault("OPENAI_BASE_URL", "https://api.deepseek.com")

# %%
#load prompts from data/prompts.yaml
import yaml
with open('data/prompts.yaml', 'r') as file:
    prompts = yaml.safe_load(file)

#load CollectedIssues.csv
df = pd.read_csv('./data/clean_CollectedIssues.csv')

# %%
#prompts

# %%
def Query(model, sys, usr, max_retries=3, retry_delay=10):

    if 'claude' in model:
        client = Anthropic(
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.openai-proxy.org/anthropic"),
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        )
        for try_idx in range(5):
            try:
                message = client.messages.create(
                    system=sys,
                    messages=[
                        {
                            "role": "user",
                            "content": usr,
                        }
                    ],
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=2048
                )

                
                final_response = message.content[0].text
                # print(final_response)
                return final_response
            except Exception as e:
                # print(e)
                
                time.sleep(2)
        return None
    

    if 'deepseek' in model:
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
    if 'gpt' in model or 'o3' in model:
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai-proxy.org/v1"),
        )
    if 'gemini' in model:
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai-proxy.org/v1"),
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

# model_list = ["gpt-4o-mini", "deepseek-chat"]
model_list = ["claude-3-7-sonnet-20250219","o3-2025-04-16","gemini-2.5-flash"]

for model in model_list:
    results = []

    for idx, row in tqdm(df.iterrows(), total=len(df)):
        url = str(row['Faults'])
        if 'issues' not in url:
            continue

        title = str(row.get('title', ''))
        created_at = str(row.get('created_at', ''))
        body = str(row.get('body', ''))
        comments_content = str(row.get('comments_content', ''))

        issue_report = f"##Issue Report\n###[Title]: {title}\n###[Created At]: {created_at}\n###[Body]:\n {body}\n###[Other Comments]:\n {comments_content}"

        user_prompt = prompts['user_input']['template'].replace("{{ISSUE REPORT}}", issue_report)
        sys_prompt = prompts['sys_classification']['template']

        response = Query(model, sys_prompt, user_prompt)

        # copy row, and append a new column 'LLM_classification' with the response
        new_row = row.copy()
        new_row['LLM_classification'] = response
        results.append(new_row)

        # save results to a new csv file
        pd.DataFrame(results).to_csv(f'./res/Labeling_{model}.csv', index=False)
        # break
