import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.core.settings import DATABASE_URL
from src.database import Base


class Engine(BaseException):
    def __init__(self):
        self.engine = create_engine(DATABASE_URL,
        pool_pre_ping = True,
        echo = os.getenv("DEBUG", "False").lower() == "true",
        pool_size = 10,
        max_overflow = 20,
        )
        self.session = sessionmaker(bind=self.engine,
                                    autocommit=False,
                                    autoflush=False,)

    def get_db(self):
        db = self.session()
        try:
            yield db
        finally:
            db.close()

    def init_db(self):
        print("=' Initializing database...")

        # PostGIS extension
        with self.engine.connect() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
                print(" PostGIS extension enabled")
            except Exception as e:
                print(f"�  PostGIS warning: {e}")

        from models import place, user  # noqa
        Base.metadata.create_all(bind=self.engine)
        print(" Database tables created successfully")
        print(" Database initialization complete")

    def test_connection(self):
        """
        Test database connection
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version();"))
                version = result.fetchone()[0]
                print(f" PostgreSQL connected: {version}")

                # Control PostGIS version
                try:
                    result = conn.execute(text("SELECT PostGIS_Version();"))
                    postgis_version = result.fetchone()[0]
                    print(f" PostGIS version: {postgis_version}")
                except:
                    print("�  PostGIS not installed")

            return True
        except Exception as e:
            print(f"L Database connection failed: {e}")
            return False