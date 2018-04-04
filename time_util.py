class Time:
    def __init__(self, hour=0, minute=0, second=0):
        self.duration = hour * 3600 + minute * 60 + second
        
    def __repr__(self):
        abs_duration = abs(self.duration)
        sign = "" if self.duration >= 0 else "-"
        
        hour, left = divmod(abs_duration, 3600)
        minute, second = divmod(left, 60)
        
        return sign + "{}:{:02}:{:02}".format(int(hour), int(minute), int(second))
    
    def __add__(self, other):
        return Time(second=self.duration + other.duration)
    
    def __sub__(self, other):
        return Time(second=self.duration - other.duration)
    
    def __neg__(self):
        return Time(second=-self.duration)
    
    def __mul__(self, other):
        return Time(second=self.duration * other)
    
    def __rmul__(self, other):
        return Time(second=self.duration * other)
    
    def __truediv__(self, other):
        return Time(second=self.duration / other)
