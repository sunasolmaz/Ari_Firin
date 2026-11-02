# src/core/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler
from .config import config

def setup_logger():
    log_config = config.get('logging')
    log_dir = os.path.dirname(log_config['file'])
    
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logger = logging.getLogger('Muhasebe')
    logger.setLevel(getattr(logging, log_config['level']))
    
    # ✅ Dosya handler - UTF-8 encoding eklendi
    file_handler = RotatingFileHandler(
        log_config['file'],
        maxBytes=log_config['max_size_mb'] * 1024 * 1024,
        backupCount=log_config['backup_count'],
        encoding='utf-8'  # <-- BU SATIRI EKLEYİN
    )
    file_handler.setLevel(logging.DEBUG)
    
    # ✅ Konsol handler - UTF-8 encoding eklendi
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    # Windows konsolunda UTF-8 desteği
    if hasattr(console_handler.stream, 'reconfigure'):
        console_handler.stream.reconfigure(encoding='utf-8')  # <-- BU SATIRI EKLEYİN
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Global logger
logger = setup_logger()