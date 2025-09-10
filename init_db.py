from modules.database import Base, engine
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    logger.info('Creating database tables...')
    Base.metadata.create_all(bind=engine)
    logger.info('Database tables created successfully!')


if __name__ == '__main__':
    init_database()
