
# import logging
# from logging import Logger

# def setup_logging(log_filename : str, loglevel: int) -> Logger:
    # formatter = logging.Formatter(        
        # fmt='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        # datefmt='%Y-%m-%d %H:%M:%S'
    # )

    # file_handler = logging.FileHandler(log_filename)
    # file_handler.setFormatter(formatter)

    # console_handler = logging.StreamHandler()
    # console_handler.setFormatter(formatter)

    # shared_logger = logging.getLogger()
    # shared_logger.setLevel(loglevel)
    # shared_logger.addHandler(file_handler)
    # shared_logger.addHandler(console_handler)
    
    # return shared_logger


# shared_logger = setup_logging("phenomate_shared.log", logging.DEBUG)