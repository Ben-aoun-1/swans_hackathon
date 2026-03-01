"""Quick Clio API smoke test — validates tokens, custom fields, stages, templates."""

import asyncio
import sys
from pathlib import Path

# Add backend/ to path so `app` is importable from tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.clio_client import ClioClient, ClioAPIError


async def main():
    async with ClioClient() as clio:

        # 1. who_am_i
        print("=" * 60)
        print("WHO AM I")
        print("=" * 60)
        me = await clio.who_am_i()
        print(f"  Name:  {me.get('name')}")
        print(f"  ID:    {me.get('id')}")
        print(f"  Email: {me.get('email')}")

        # 2. get_custom_fields
        print("\n" + "=" * 60)
        print("CUSTOM FIELDS")
        print("=" * 60)
        fields = await clio.get_custom_fields()
        print(f"  Total: {len(fields)}")
        for f in fields[:5]:
            print(f"    - {f.get('name')} (id={f.get('id')}, type={f.get('field_type')})")
        if len(fields) > 5:
            print(f"    ... and {len(fields) - 5} more")

        # 3. build_field_id_map
        print("\n" + "=" * 60)
        print("FIELD ID MAP")
        print("=" * 60)
        field_map = await clio.build_field_id_map()
        for name, fid in sorted(field_map.items()):
            print(f"    {name:40s} → {fid}")

        # 4. get_matter_stages
        print("\n" + "=" * 60)
        print("MATTER STAGES")
        print("=" * 60)
        stages = await clio.get_matter_stages()
        for s in stages:
            print(f"    {s.get('name'):30s} (id={s.get('id')}, order={s.get('order')})")

        # 5. get_practice_areas
        print("\n" + "=" * 60)
        print("PRACTICE AREAS")
        print("=" * 60)
        areas = await clio.get_practice_areas()
        for a in areas:
            print(f"    {a.get('name'):30s} (id={a.get('id')})")

        # 6. get_document_templates
        print("\n" + "=" * 60)
        print("DOCUMENT TEMPLATES")
        print("=" * 60)
        templates = await clio.get_document_templates()
        if templates:
            for t in templates:
                print(f"    {t.get('name'):40s} (id={t.get('id')})")
        else:
            print("    (none found)")

    print("\n" + "=" * 60)
    print("SMOKE TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ClioAPIError as e:
        print(f"\nClio API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        sys.exit(1)
