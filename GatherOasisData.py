import pandas as pd
import requests
import io
import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import zipfile
import time
import pandas as pd
import pytz


class GatherOASISData:
    def __init__(self, start_date, end_date, report_type, market_run_id, tac_area_name = 'TIDC'):
        
        self.start_date = start_date #format YYYYMMDD, ex: 20230514. Assumes midnight UTC for hr.
        self.end_date = end_date # same as above ^
        self.report_type = report_type #report type, ex. SLD_FCST (forecast)
        self.market_run_id = market_run_id #time ahead: 2DA, 7DA, DAM, ACTUAL, RTM 
        self.tac_area_name = tac_area_name #utility area, ex. TIDC, PGE, etc.
        self.folder_name = f"{self.start_date}_{self.end_date}_{self.report_type}_{self.market_run_id}"
#         self.name_space = {"http://www.caiso.com/soa/OASISReport_v1.xsd"}
    
    def generate_query_urls(self):
        
        '''
        Generates a query for CAISO OASIS API
        '''
        query_urls = []
        query_dates = self.create_date_subsets() #list of list of queries dates, depending on report type
        
        for query in range(len(query_dates)):
            
            #adjusting from UTC to PST (-0800) in start/end
            url = f"http://oasis.caiso.com/oasisapi/SingleZip?queryname={self.report_type}&market_run_id={self.market_run_id}&startdatetime={query_dates[query][0]}T00:00-0800&enddatetime={query_dates[query][1]}T00:00-0800&version=1"
                  # "http://oasis.caiso.com/oasisapi/SingleZip?queryname=SLD_FCST&market_run_id=DAM&resultfor mat=6&startdatetime=20230415T07:00-0000&enddatetime=20230416T07:00-0000&version=1"
            query_urls.append(url)
        
        return query_urls
        
        
    def create_date_subsets(self):
        '''
        If report length is > 30 days, this method splits the range of dates into sizes compatible with OASIS API
        '''
        date_subsets = []
        
        #convert times to datetime
        datetime_start_date = datetime.strptime(self.start_date, '%Y%m%d')
        datetime_end_date = datetime.strptime(self.end_date, '%Y%m%d')
        
        #days between dates
        days_delta = (datetime_end_date - datetime_start_date).days
        
        #Demand Forecast
        if self.report_type == 'SLD_FCST':
            max_days = 30
            
            #if there is a need to split into multiple subsets
            if days_delta > max_days:
                start_date = datetime_start_date #convert to dt
                
                while start_date < datetime_end_date:
                    
                    #ensures if days =<30, the end date doesnt go over end date 
                    end_date = min(start_date + timedelta(days=max_days - 1), datetime_end_date) 
                    
                    #add start and end in list into date_subsets and format into query-able format
                    date_subsets.append([start_date.strftime('%Y%m%d'), (end_date + timedelta(days=1)).strftime('%Y%m%d') ]) 
                    start_date = end_date# + timedelta(days=1) #start date is end date + 1 day
                
                
                
            
            #if days difference less than 31 days, return original dates
            else:
                date_subsets.append([self.start_date, self.end_date])
            
            
        return date_subsets
        
            
    def download_extract_zip(self):
        '''
        Downlaods the query (zip file) and extracts to folder 
        
        '''
        query_urls = self.generate_query_urls()
        
        for url in query_urls:
            try:
                response = requests.get(url)

                #see if request was successful
                if response.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                        #exract to data folder
                        zip_ref.extractall(self.folder_name)
                        print(f'Downloaded {url}')
                
                else:
                    print(f"Failed to download from {url}. Status code: {response.status_code}")
            except requests.RequestException as e:
                print(f"Request error for {url}: {e}")
            except zipfile.BadZipFile:
                print(f"Invalid ZIP file from {url}")
            
            #rate limits
            time.sleep(5)
        time.sleep(1)
        
            
    def get_XML(self):
        '''
        Gets the file paths for each zip file extracted
        '''
        file_paths = []
        xml_file_names = [file for file in os.listdir(self.folder_name)]
        for file_name in xml_file_names:
            file_paths.append(os.path.join(self.folder_name, file_name))
            
        return file_paths
            
    
    def parse_XML(self, XML_files):
        '''
        Parses all XML files - extracting data and returning a dataframe
        '''
        namespace = '{http://www.caiso.com/soa/OASISReport_v1.xsd}' #xmlns
        extracted_data = [] #store extracted data
        
        for xml in XML_files:
            print(f'Extracting data from {xml}')
            tree = ET.parse(xml)
            root = tree.getroot()

            

            message_payload = root.find(namespace + 'MessagePayload')
            rto = message_payload.find(namespace +'RTO')
            for report_item in rto.findall(namespace + 'REPORT_ITEM'):
                for report_data in report_item.findall(namespace + 'REPORT_DATA'):
                    
                    #makes for a simpler dataframe after
                    if self.market_run_id == 'ACTUAL':
                        key = 'ACTUAL_MW'
                    elif self.market_run_id == 'DAM':
                        key = 'DAM_MW'
                    else:
                        key = '2DA_MW'
                    tac_area = report_data.find(namespace + 'RESOURCE_NAME').text
                    
                    if tac_area == self.tac_area_name:
                        data_item = report_data.find(namespace + 'DATA_ITEM').text if report_data.find(namespace + 'DATA_ITEM') is not None else 'N/A'
                        interval_start = report_data.find(namespace + 'INTERVAL_START_GMT').text if report_data.find(namespace + 'INTERVAL_START_GMT') is not None else 'N/A'
#                         interval_end = report_data.find(namespace + 'INTERVAL_END_GMT').text if report_data.find(namespace + 'INTERVAL_END_GMT') is not None else 'N/A'
                        value = report_data.find(namespace + 'VALUE').text if report_data.find(namespace + 'VALUE') is not None else 'N/A'
                        
                        
                        #convert GMT to PST
                        interval_start_pacific = self.convert_GMT_PST(interval_start)
#                         interval_end_pacific = self.convert_GMT_PST(interval_end)
                        print(f"Original UTC time: {interval_start} => Converted PST time: {interval_start_pacific}")

                        #store in list
                        extracted_data.append({
#                             'DESCRIPTION': data_item,
#                             'TAC_AREA': tac_area,
                            'TIME': interval_start_pacific,
#                             'INTERVAL_END_PST': interval_end_pacific,
                            key : float(value)
                        })
            print(f'Extracted TIDC data from {xml}')
        if not extracted_data:
            print("No data extracted from XML files.")
            return pd.DataFrame()  # 
        
        df = pd.DataFrame(extracted_data)
        
        #convert data types
        # df['TIME'] = pd.to_datetime(df['TIME'])
#         df['INTERVAL_END_PST'] = pd.to_datetime(df['INTERVAL_END_PST'])
        df = df.set_index('TIME')
        df.sort_index(inplace=True)
        return df
    
        
        
        
    def convert_GMT_PST(self, gmt_str):
        '''
        converts GMT to PST
        '''
        gmt_time = datetime.strptime(gmt_str, "%Y-%m-%dT%H:%M:%S-00:00")
        
        #using pytz to account for DST
        pacific = pytz.timezone("America/Los_Angeles")
        
        #convert
        pacific_time = gmt_time.replace(tzinfo=pytz.utc).astimezone(pacific)
        
        return pacific_time
    
    
    def process_data(self):
        """
        1. Generates query URLs
        2. Downloads and extracts ZIP files
        3. Parses XML files to extract data
        4. Cleans and formats the data into a df
        """
        #generate and extract and dl data
        self.download_extract_zip()

        #gather list of xmls
        XML_files = self.get_XML()

        #prarse xmls and return df
        df = self.parse_XML(XML_files)
        
        df = df[~df.index.duplicated(keep='first')]


        return df
        
        

        
    
    