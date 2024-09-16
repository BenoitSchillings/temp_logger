import serial
import time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from collections import deque
from datetime import datetime, timedelta
import numpy as np
import math
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QComboBox, QHBoxLayout
from PyQt5.QtCore import QTimer
import sys

def calculate_dew_point(temp, rh):
    a = 17.27
    b = 237.7
    alpha = ((a * temp) / (b + temp)) + math.log(rh/100.0)
    return (b * alpha) / (a - alpha)

def calculate_absolute_humidity(temp, rh):
    return (6.112 * math.exp((17.67 * temp) / (temp + 243.5)) * rh * 2.1674) / (273.15 + temp)

class InteractivePlot(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interactive Sensor Data Plot")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Add time range selector
        selector_layout = QHBoxLayout()
        self.time_range_selector = QComboBox()
        self.time_range_selector.addItems(["Last 1 minute", "Last 5 minutes", "Last 20 minutes", "Last 1 hour", "Last 4 hours"])
        self.time_range_selector.setCurrentIndex(4)  # Default to 4 hours
        self.time_range_selector.currentIndexChanged.connect(self.update_time_range)
        selector_layout.addWidget(self.time_range_selector)
        main_layout.addLayout(selector_layout)

        self.fig = Figure(figsize=(12, 16))
        self.canvas = FigureCanvas(self.fig)
        main_layout.addWidget(self.canvas)

        self.ax1 = self.fig.add_subplot(411)
        self.ax2 = self.fig.add_subplot(412)
        self.ax3 = self.fig.add_subplot(413)
        self.ax4 = self.fig.add_subplot(414)

        self.temp_line, = self.ax1.plot([], [], 'r-', label='Temperature')
        self.temp_avg_line, = self.ax1.plot([], [], 'b-', label='20s Moving Avg')
        self.rh_line, = self.ax2.plot([], [], 'b-', label='Relative Humidity')
        self.ah_line, = self.ax3.plot([], [], 'g-', label='Absolute Humidity')
        self.dp_line, = self.ax4.plot([], [], 'm-', label='Dew Point')

        self.ax1.set_ylabel('Temperature (°C)')
        self.ax2.set_ylabel('Relative Humidity (%)')
        self.ax3.set_ylabel('Absolute Humidity (g/m³)')
        self.ax4.set_ylabel('Dew Point (°C)')
        self.ax4.set_xlabel('Time')

        for ax in (self.ax1, self.ax2, self.ax3, self.ax4):
            ax.legend()
            ax.grid(True)

        date_formatter = mdates.DateFormatter('%H:%M:%S')
        for ax in (self.ax1, self.ax2, self.ax3, self.ax4):
            ax.xaxis.set_major_formatter(date_formatter)

        self.fig.tight_layout()

        # Initialize data structures
        self.max_points = 4 * 60 * 60  # 4 hours of data
        self.timestamps = deque(maxlen=self.max_points)
        self.temperatures = deque(maxlen=self.max_points)
        self.temp_avg = deque(maxlen=self.max_points)
        self.rel_humidities = deque(maxlen=self.max_points)
        self.abs_humidities = deque(maxlen=self.max_points)
        self.dew_points = deque(maxlen=self.max_points)

        # Connect to serial port
        self.ser = serial.Serial('/dev/ttyACM1', 9600)
        
        # Start updating plot
        self.start_time = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(100)  # Update every 100 ms

        self.time_range = timedelta(hours=4)  # Default time range

    def update_plot(self):
        if self.ser.in_waiting > 0:
            line = self.ser.readline().decode('utf-8').strip()
            parts = line.split(',')
            
            if len(parts) == 4:
                timestamp, temp, rh, _ = parts
                temp = float(temp)
                rh = float(rh)
                
                current_time = datetime.now()
                if self.start_time is None:
                    self.start_time = current_time
                
                ah = calculate_absolute_humidity(temp, rh)
                dp = calculate_dew_point(temp, rh)
                
                self.timestamps.append(current_time)
                self.temperatures.append(temp)
                self.rel_humidities.append(rh)
                self.abs_humidities.append(ah)
                self.dew_points.append(dp)
                
                # Calculate 20-second moving average
                twenty_sec_ago = current_time - timedelta(seconds=20)
                recent_temps = [t for t, ts in zip(self.temperatures, self.timestamps) if ts > twenty_sec_ago]
                if recent_temps:
                    avg_temp = sum(recent_temps) / len(recent_temps)
                    self.temp_avg.append(avg_temp)
                else:
                    self.temp_avg.append(temp)  # If not enough data, use current temp
                
                self.temp_line.set_data(self.timestamps, self.temperatures)
                self.temp_avg_line.set_data(self.timestamps, self.temp_avg)
                self.rh_line.set_data(self.timestamps, self.rel_humidities)
                self.ah_line.set_data(self.timestamps, self.abs_humidities)
                self.dp_line.set_data(self.timestamps, self.dew_points)
                
                self.adjust_y_axis_ranges()
                
                for ax in (self.ax1, self.ax2, self.ax3, self.ax4):
                    ax.set_xlim(current_time - self.time_range, current_time)
                
                self.fig.canvas.draw()
                
                print(f"Time: {current_time.strftime('%H:%M:%S')}")
                print(f"Temperature: {temp:.2f}°C")
                print(f"20s Avg Temperature: {self.temp_avg[-1]:.2f}°C")
                print(f"Relative Humidity: {rh:.2f}%")
                print(f"Absolute Humidity: {ah:.2f} g/m³")
                print(f"Dew Point: {dp:.2f}°C")
                print("-" * 30)

    def adjust_y_axis_ranges(self):
        current_time = datetime.now()
        start_time = current_time - self.time_range

        # Filter data for the current time range
        visible_timestamps = [t for t in self.timestamps if t >= start_time]
        visible_temps = [t for t, ts in zip(self.temperatures, self.timestamps) if ts >= start_time]
        visible_temp_avgs = [t for t, ts in zip(self.temp_avg, self.timestamps) if ts >= start_time]
        visible_rhs = [rh for rh, ts in zip(self.rel_humidities, self.timestamps) if ts >= start_time]
        visible_ahs = [ah for ah, ts in zip(self.abs_humidities, self.timestamps) if ts >= start_time]
        visible_dps = [dp for dp, ts in zip(self.dew_points, self.timestamps) if ts >= start_time]

        # Adjust y-axis ranges
        if visible_temps:
            temp_min = min(min(visible_temps), min(visible_temp_avgs))
            temp_max = max(max(visible_temps), max(visible_temp_avgs))
            self.ax1.set_ylim(temp_min - 1, temp_max + 1)

        if visible_rhs:
            rh_min, rh_max = min(visible_rhs), max(visible_rhs)
            self.ax2.set_ylim(max(0, rh_min - 5), min(100, rh_max + 5))

        if visible_ahs:
            ah_min, ah_max = min(visible_ahs), max(visible_ahs)
            self.ax3.set_ylim(ah_min - 0.5, ah_max + 0.5)

        if visible_dps:
            dp_min, dp_max = min(visible_dps), max(visible_dps)
            self.ax4.set_ylim(dp_min - 1, dp_max + 1)

    def update_time_range(self, index):
        if index == 0:
            self.time_range = timedelta(minutes=1)
        elif index == 1:
            self.time_range = timedelta(minutes=5)
        elif index == 2:
            self.time_range = timedelta(minutes=20)
        elif index == 3:
            self.time_range = timedelta(hours=1)
        else:
            self.time_range = timedelta(hours=4)
        
        # Update the plot with the new time range
        current_time = datetime.now()
        for ax in (self.ax1, self.ax2, self.ax3, self.ax4):
            ax.set_xlim(current_time - self.time_range, current_time)
        
        self.adjust_y_axis_ranges()
        self.canvas.draw()

    def closeEvent(self, event):
        self.timer.stop()
        self.ser.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = InteractivePlot()
    main_window.show()
    sys.exit(app.exec_())