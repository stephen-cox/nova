"""Network and IP-related tools

These tools provide network information and IP address analysis capabilities.
"""

import httpx

from nova.models.tools import PermissionLevel, ToolCategory, ToolExample
from nova.tools import tool


@tool(
    description="Get your current public IP address",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.INFORMATION,
    tags=["network", "ip", "current"],
    examples=[
        ToolExample(
            description="Get current public IP",
            arguments={},
            expected_result="Your current public IP address",
        ),
    ],
)
async def get_my_ip() -> str:
    """
    Get your current public IP address.

    Returns:
        Current public IP address
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://ipapi.co/ip/", timeout=10.0)

            if response.status_code != 200:
                return f"Failed to get IP address. HTTP status: {response.status_code}"

            return response.text.strip()

    except httpx.RequestError as e:
        return f"Network error occurred: {str(e)}"
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"


@tool(
    description="Get your current location (city, region, country)",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.INFORMATION,
    tags=["location", "current", "city", "country"],
    examples=[
        ToolExample(
            description="Get current location",
            arguments={},
            expected_result="Your current city, region, and country",
        ),
    ],
)
async def get_my_location() -> str:
    """
    Get your current location based on your IP address.

    Returns:
        Current location including city, region, and country
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://ipapi.co/json/", timeout=10.0)

            if response.status_code != 200:
                return (
                    f"Failed to get location data. HTTP status: {response.status_code}"
                )

            data = response.json()

            # Check for API error
            if "error" in data:
                return f"API Error: {data.get('reason', 'Unknown error')}"

            # Format location information
            city = data.get("city")
            region = data.get("region")
            country = data.get("country_name")

            if city and region and country:
                return f"{city}, {region}, {country}"
            elif city and country:
                return f"{city}, {country}"
            elif country:
                return country
            else:
                return "Location information not available"

    except httpx.RequestError as e:
        return f"Network error occurred: {str(e)}"
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"


@tool(
    description="Get your current timezone",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.INFORMATION,
    tags=["timezone", "current", "time"],
    examples=[
        ToolExample(
            description="Get current timezone",
            arguments={},
            expected_result="Your current timezone (e.g., America/New_York)",
        ),
    ],
)
async def get_my_timezone() -> str:
    """
    Get your current timezone based on your IP address.

    Returns:
        Current timezone identifier
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://ipapi.co/timezone/", timeout=10.0)

            if response.status_code != 200:
                return (
                    f"Failed to get timezone data. HTTP status: {response.status_code}"
                )

            timezone = response.text.strip()
            return timezone if timezone else "Timezone information not available"

    except httpx.RequestError as e:
        return f"Network error occurred: {str(e)}"
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"


@tool(
    description="Get your current country information",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.INFORMATION,
    tags=["country", "current", "location"],
    examples=[
        ToolExample(
            description="Get current country",
            arguments={},
            expected_result="Your current country name and code",
        ),
    ],
)
async def get_my_country() -> str:
    """
    Get your current country based on your IP address.

    Returns:
        Current country name and country code
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://ipapi.co/json/", timeout=10.0)

            if response.status_code != 200:
                return (
                    f"Failed to get country data. HTTP status: {response.status_code}"
                )

            data = response.json()

            # Check for API error
            if "error" in data:
                return f"API Error: {data.get('reason', 'Unknown error')}"

            country_name = data.get("country_name")
            country_code = data.get("country_code")

            if country_name and country_code:
                return f"{country_name} ({country_code})"
            elif country_name:
                return country_name
            else:
                return "Country information not available"

    except httpx.RequestError as e:
        return f"Network error occurred: {str(e)}"
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"


@tool(
    description="Look up location information for any IP address",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.INFORMATION,
    tags=["network", "ip", "location", "lookup"],
    examples=[
        ToolExample(
            description="Look up Google DNS server location",
            arguments={"ip_address": "8.8.8.8"},
            expected_result="Location information for the specified IP address",
        ),
    ],
)
async def lookup_ip_address(ip_address: str) -> str:
    """
    Look up location and network information for any IP address.

    Args:
        ip_address: IP address to look up

    Returns:
        Location information including city, country, timezone, and network details
    """
    try:
        url = f"https://ipapi.co/{ip_address}/json/"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)

            if response.status_code != 200:
                return f"Failed to get IP location data. HTTP status: {response.status_code}"

            data = response.json()

            # Check for API error
            if "error" in data:
                return f"API Error: {data.get('reason', 'Unknown error')}"

            # Format the response
            result = []
            result.append(f"IP Address: {ip_address}")

            # Location information
            city = data.get("city")
            region = data.get("region")
            country = data.get("country_name")
            if city and region and country:
                result.append(f"Location: {city}, {region}, {country}")
            elif country:
                result.append(f"Country: {country}")

            # Additional details
            if data.get("country_code"):
                result.append(f"Country Code: {data.get('country_code')}")

            if data.get("timezone"):
                result.append(f"Timezone: {data.get('timezone')}")

            if data.get("latitude") and data.get("longitude"):
                result.append(
                    f"Coordinates: {data.get('latitude')}, {data.get('longitude')}"
                )

            if data.get("org"):
                result.append(f"Organization: {data.get('org')}")

            if data.get("asn"):
                result.append(f"ASN: {data.get('asn')}")

            return "\n".join(result)

    except httpx.RequestError as e:
        return f"Network error occurred: {str(e)}"
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"
