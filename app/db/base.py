import json
from contextlib import suppress

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from config import settings

engine = create_async_engine(settings.DSN.DATABASE_ASYNC, echo=False)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)

Base = declarative_base()

cascade = 'all, delete-orphan'


async def load_test_fixtures():
    fixtures = settings.PATHS.FIXTURES_DIR.rglob('*.json')
    models = Base.__subclasses__()

    for fixture in fixtures:
        content = json.loads(fixture.read_bytes())
        for data_pack in content:
            model = next(filter(lambda m: data_pack['table'] == m.__tablename__, models))
            rows = data_pack['rows']

            for row in rows:
                with suppress(IntegrityError):
                    async with engine.connect() as connection:
                        await connection.execute(insert(model).values(**row))
                await engine.dispose()
