from database.db import create_tables
import logging

logger = logging.getLogger(__name__)


create_tables()
logger.info("Tables created automatically.")
