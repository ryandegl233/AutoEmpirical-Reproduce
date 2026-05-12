from openai import OpenAI

client = OpenAI(
    api_key="sk-vdDHkpu2DLnasqmeqIJro0ebA11EUe1CDEHLMZ0KQdZ149VU",
    base_url="https://yunwu.ai/v1"
)

models = client.models.list()

for model in models.data:
    print(model.id)
