#!/usr/bin/env python3
"""Extract Chrome session cookies for a given domain.

Usage:
  extract.py <domain> [--json] [--profile <name>]

Default output: Cookie header value string (name=value; name=value; ...)
  suitable for: curl -H "Cookie: $(extract.py example.com)" ...

--json output: JSON array of {name, value, domain, path, secure, expires}
"""
import argparse
import json
import sys

try:
    import browser_cookie3
except ImportError:
    print(
        "browser_cookie3 is not installed. Run: pip3 install --user browser-cookie3",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    parser = argparse.ArgumentParser(
        description="Extract Chrome cookies for a domain (macOS only)."
    )
    parser.add_argument("domain", help="Domain to extract cookies for (e.g. airtable.com)")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON array instead of Cookie header value",
    )
    parser.add_argument(
        "--profile",
        default="Default",
        help="Chrome profile name (default: Default)",
    )
    args = parser.parse_args()

    try:
        cookie_jar = browser_cookie3.chrome(
            domain_name=args.domain,
            profile=args.profile,
        )
    except PermissionError as exc:
        print(
            f"Keychain access denied: {exc}\n"
            "Ensure you clicked 'Always Allow' on the Keychain dialog.",
            file=sys.stderr,
        )
        sys.exit(3)
    except Exception as exc:
        # Catch broad exceptions from browser_cookie3 (locked DB, missing file, etc.)
        print(f"Error reading Chrome cookies: {exc}", file=sys.stderr)
        sys.exit(1)

    cookies = list(cookie_jar)

    if not cookies:
        print(
            f"No cookies found for domain '{args.domain}'. "
            "Are you logged in to this site in Chrome?",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.json_output:
        output = [
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
                "secure": bool(c.secure),
                "expires": c.expires,
            }
            for c in cookies
        ]
        print(json.dumps(output))
    else:
        header_value = "; ".join(f"{c.name}={c.value}" for c in cookies)
        print(header_value, end="")


if __name__ == "__main__":
    main()
