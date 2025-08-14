import logging
import os
import time
import threading
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinkedInScraper:
    def __init__(self):
        """Initialize the LinkedIn scraper."""
        load_dotenv()
        
        # Initialize state variables
        self.driver = None
        self.is_searching = False
        self.status = "Pronto"
        self.message = "Aguardando início da busca"
        self.error = None
        self.progress = 0
        self.results = []
        self.cookies = None
        self.logger = logger

    def _init_driver(self):
        """Initialize the Chrome WebDriver with optimized settings."""
        try:
            chrome_options = Options()
            
            # Basic options
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # Stealth options
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-extensions')
            
            # Performance options
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Initialize the driver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set timeouts
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            
            return driver
            
        except Exception as e:
            self.logger.error(f"Failed to initialize driver: {str(e)}")
            if 'driver' in locals() and driver:
                try:
                    driver.quit()
                except:
                    pass
            raise

    def _login(self):
        """Login to LinkedIn."""
        if not self.driver:
            self.driver = self._init_driver()
            
        try:
            # Check for credentials
            email = os.getenv('LINKEDIN_EMAIL')
            password = os.getenv('LINKEDIN_PASSWORD')
            
            if not email or not password:
                raise ValueError("LinkedIn credentials not found in environment variables")
            
            # Navigate to login page
            self.driver.get('https://www.linkedin.com/login')
            time.sleep(2)
            
            # Fill in login form
            username = self.driver.find_element(By.ID, "username")
            username.clear()
            username.send_keys(email)
            
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(password)
            
            # Click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            time.sleep(3)
            
            # Check if login was successful
            if "feed" not in self.driver.current_url:
                raise ValueError("Login failed: Invalid credentials")
            
            # Add cookies to session
            self.cookies = self.driver.get_cookies()
            return True
            
        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            raise

    def _navigate_to_jobs(self):
        """Navigate to LinkedIn Jobs page."""
        self.driver.get("https://www.linkedin.com/jobs/")
        time.sleep(2)

    def _fill_search_form(self, keywords, location=None):
        """Fill in the job search form."""
        try:
            # Fill keywords
            search_input = self.driver.find_element(By.CLASS_NAME, "jobs-search-box__text-input")
            search_input.clear()
            search_input.send_keys(keywords)
            time.sleep(1)
            
            # Fill location if provided
            if location:
                location_input = self.driver.find_element(By.CLASS_NAME, "jobs-search-box__location-input")
                location_input.clear()
                location_input.send_keys(location)
                time.sleep(1)
            
            # Click search button
            search_button = self.driver.find_element(By.CLASS_NAME, "jobs-search-box__submit-button")
            search_button.click()
            time.sleep(3)
            
        except Exception as e:
            self.logger.error(f"Error filling search form: {str(e)}")
            raise

    def _apply_filters(self, filters):
        """Apply job search filters."""
        try:
            if filters.get('max_date'):
                # Click date filter
                date_filter = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Data de publicação']")
                date_filter.click()
                time.sleep(1)
                
                # Select date option
                date_option = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{filters['max_date']}']")
                date_option.click()
                time.sleep(1)
            
            if filters.get('distance'):
                # Click distance filter
                distance_filter = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Distância']")
                distance_filter.click()
                time.sleep(1)
                
                # Select distance option
                distance_option = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{filters['distance']}']")
                distance_option.click()
                time.sleep(1)
            
            if filters.get('job_type'):
                # Click job type filter
                type_filter = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Tipo de trabalho']")
                type_filter.click()
                time.sleep(1)
                
                # Select job types
                for job_type in filters['job_type']:
                    type_option = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{job_type}']")
                    type_option.click()
                    time.sleep(0.5)
            
            if filters.get('place'):
                # Click place filter
                place_filter = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Local']")
                place_filter.click()
                time.sleep(1)
                
                # Select places
                for place in filters['place']:
                    place_option = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{place}']")
                    place_option.click()
                    time.sleep(0.5)
            
            # Click show results button
            show_results = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Mostrar resultados']")
            show_results.click()
            time.sleep(3)
            
        except Exception as e:
            self.logger.error(f"Error applying filters: {str(e)}")
            raise

    def _search_jobs_thread(self, keywords, location, filters):
        """Thread para buscar vagas"""
        try:
            self._navigate_to_jobs()
            self._fill_search_form(keywords, location)
            
            if filters:
                self._apply_filters(filters)
            
            self.results = []
            processed_count = 0
            limit = int(filters.get('limit_jobs', 10))
            
            while processed_count < limit:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, '.jobs-search__results-list > li')
                
                if not job_cards:
                    self.status = 'error'
                    self.message = 'Nenhuma vaga encontrada'
                    break
                
                for card in job_cards:
                    if processed_count >= limit:
                        break
                        
                    try:
                        job_data = {
                            'title': card.find_element(By.CSS_SELECTOR, '.job-card-list__title').text.strip(),
                            'company': card.find_element(By.CSS_SELECTOR, '.job-card-container__company-name').text.strip(),
                            'location': card.find_element(By.CSS_SELECTOR, '.job-card-container__metadata-item').text.strip(),
                            'link': card.find_element(By.CSS_SELECTOR, '.job-card-list__title').get_attribute('href')
                        }
                        
                        self.results.append(job_data)
                        processed_count += 1
                        
                        self.progress = int((processed_count / limit) * 100)
                        self.message = f'Processando vaga {processed_count} de {limit}'
                        
                    except Exception as e:
                        self.logger.error(f'Erro ao processar vaga: {str(e)}')
                        continue
                
                if processed_count < limit:
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Próxima"]')
                        if not next_button.is_enabled():
                            break
                        next_button.click()
                        time.sleep(2)
                    except:
                        break
            
            self.status = 'complete'
            self.message = f'Busca concluída. {len(self.results)} vagas encontradas.'
            
        except Exception as e:
            self.logger.error(f'Erro na busca de vagas: {str(e)}')
            self.status = 'error'
            self.message = f'Erro na busca: {str(e)}'
        finally:
            if hasattr(self, 'driver'):
                self.driver.quit()

    def search_jobs(self, keywords, location=None, filters=None):
        """Start a job search with the given parameters."""
        if self.is_searching:
            raise RuntimeError("A search is already in progress")
        
        self.is_searching = True
        self.status = "Iniciando busca de vagas..."
        self.message = "Iniciando busca..."
        self.progress = 0
        self.error = None
        self.results = []
        
        try:
            # Initialize driver if needed
            if not self.driver:
                self.driver = webdriver.Chrome()
            
            # Start search thread
            search_thread = threading.Thread(
                target=self._search_jobs_thread,
                args=(keywords, location, filters),
                daemon=True
            )
            search_thread.start()
            return True
            
        except Exception as e:
            self.is_searching = False
            self.error = str(e)
            self.logger.error(f"Failed to start job search: {str(e)}")
            raise

    def stop_search(self):
        """Stop the current search operation."""
        self.is_searching = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
        return True

    def get_status(self):
        """Get the current status of the search operation."""
        return {
            'is_searching': self.is_searching,
            'status': self.status,
            'message': self.message,
            'error': self.error,
            'progress': self.progress
        }

    def get_results(self):
        """Get the search results."""
        return self.results.copy()

    def __del__(self):
        """Clean up resources when the object is destroyed."""
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass 


        