from meteostat import Stations, Daily, Hourly
from datetime import datetime
import pytz


class GatherWeatherConditons():
    def __init__(self,  start_date, end_date, time_steps, station_id='KMCE0'):
        self.station_id = station_id #set for Merced by default
        self.start_date = start_date #YYYYMMDD
        self.end_date = end_date #YYYYMMDD
        self.time_steps = time_steps #DAILY, HOURLY, 15MIN, 5MIN
        
        
    def get_data(self):
        
        #format times for meteostat w/ datetime
        start_date = datetime.strptime(str(self.start_date), '%Y%m%d')
        end_date = datetime.strptime(str(self.end_date), '%Y%m%d')
        
        #daily
        if self.time_steps == 'DAILY':
            data = Daily(self.station_id, start_date, end_date)
            return data.fetch()
        
        #all other granularities use hourly
        data = Hourly(self.station_id, start_date, end_date)
        data = data.fetch()

        #hourly
        if self.time_steps == 'HOURLY':
            return data
        
        #15m 
        elif self.time_steps == '15MIN':
            return self.interpolate_data(data)
        
        #5m
        else:
            return self.interpolate_data(data)
                   
    def interpolate_data(self, hourly_data):
        #resample data
        if self.time_steps == '15MIN':
            resampled_data = hourly_data.resample('15T').asfreq()
        else:
            resampled_data = hourly_data.resample('5T').asfreq()
            
        #interpolate missing values linearly 
        interpolated_data = resampled_data.interpolate(method='linear')

        return interpolated_data
    
    
    def clean_df(self, df):
        
        
        if self.time_steps == 'DAILY':
            
            #drop unncessary columns
            df.drop(columns=['prcp', 'snow', 'wdir', 'wspd', 'wpgt', 'pres','tsun'], inplace=True)
            
            #convert to F, DAILY has 'tavg', 'tmin', 'tmax'
            df[df.columns] = df[df.columns] * 9/5 + 32 
            
            return df
        
        else:
            df.drop(columns=['dwpt', 'rhum', 'prcp', 'snow', 'wdir', 'wspd', 'wpgt', 'pres','tsun', 'coco'],inplace=True)
            
            #convert to F
            df['temp'] = df['temp'] * 9/5 + 32
            
            return df
        
    def convert_UTC_to_PST(self, df):
        
        #convert times from UTC to PST
        utc = pytz.utc
        pst = pytz.timezone('America/Los_Angeles')
        df.index = df.index.tz_localize(utc).tz_convert(pst)
        df.index = df.index.tz_localize(None)
        return df
    
    def fetch_and_process_data(self):
        
        #grab, clean, and convert times on data
        data = self.get_data()
        clean_data = self.clean_df(data)
        return self.convert_UTC_to_PST(clean_data)