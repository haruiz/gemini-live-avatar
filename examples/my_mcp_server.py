from fastapi import FastAPI, HTTPException
from fastapi_mcp import FastApiMCP
import httpx
app = FastAPI()


@app.get("/currency/{country}", operation_id="get_currency_country", description="Get the currency for a specific country")
async def get_currency_country(country: str):
    url = "https://restcountries.com/v3.1/name/{}".format(country)
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="Country not found")

    data = response.json()
    if not data or "currencies" not in data[0]:
        raise HTTPException(status_code=404, detail="Currency information not available")

    currencies = data[0]["currencies"]
    currency_names = [val.get("name") for val in currencies.values() if val.get("name")]
    return {"country": country, "currencies": currency_names}



# Add the MCP server to your FastAPI app
mcp = FastApiMCP(
    app,
    name="MCPFastAPI",
    include_operations=["get_currency_country"],
    description="MCP Server for FastAPI Example",
    describe_all_responses=True,
    describe_full_response_schema=True,
)

# Mount the MCP server to your FastAPI app
mcp.mount()

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)