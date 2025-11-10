import finnhub
finnhub_client = finnhub.Client(api_key="d48ojphr01qnpsnopla0d48ojphr01qnpsnoplag")

print(finnhub_client.company_peers('HIMS'))