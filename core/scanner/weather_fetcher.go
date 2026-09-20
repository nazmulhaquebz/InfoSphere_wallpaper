package main

import (
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type Config struct {
	ShowWeather bool   `json:"show_weather"`
	WeatherCity string `json:"weather_city"`
}

type WeatherData struct {
	Temp       string `json:"temp"`
	FeelsLike  string `json:"feels_like"`
	Humidity   string `json:"humidity"`
	Condition  string `json:"condition"`
	Wind       string `json:"wind"`
	WindDir    string `json:"wind_dir"`
	Visibility string `json:"visibility"`
	Pressure   string `json:"pressure"`
	UVIndex    string `json:"uv_index"`
	Location   string `json:"location"`
	IP         string `json:"ip,omitempty"`
	ISP        string `json:"isp,omitempty"`
}

type IPGeoResult struct {
	IP        string
	City      string
	District  string
	Region    string
	Country   string
	Latitude  float64
	Longitude float64
	ISP       string
}

func degToCompass(deg float64) string {
	val := int((deg + 11.25) / 22.5)
	directions := []string{"N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"}
	return directions[val%16]
}

func wmoToCondition(code int) string {
	switch code {
	case 0:
		return "Clear Sky"
	case 1:
		return "Mainly Clear"
	case 2:
		return "Partly Cloudy"
	case 3:
		return "Overcast"
	case 45, 48:
		return "Fog"
	case 51:
		return "Light Drizzle"
	case 53:
		return "Moderate Drizzle"
	case 55:
		return "Dense Drizzle"
	case 56, 57:
		return "Freezing Drizzle"
	case 61:
		return "Slight Rain"
	case 63:
		return "Moderate Rain"
	case 65:
		return "Heavy Rain"
	case 66, 67:
		return "Freezing Rain"
	case 71:
		return "Slight Snow"
	case 73:
		return "Moderate Snow"
	case 75:
		return "Heavy Snow"
	case 77:
		return "Snow Grains"
	case 80:
		return "Light Rain Showers"
	case 81:
		return "Moderate Rain Showers"
	case 82:
		return "Violent Rain Showers"
	case 85, 86:
		return "Snow Showers"
	case 95:
		return "Thunderstorm"
	case 96, 99:
		return "Thunderstorm with Hail"
	default:
		return "Clear"
	}
}

// geolocateByIP dynamically checks the public IP address across multiple authoritative IP-geo providers
func geolocateByIP() (*IPGeoResult, error) {
	client := &http.Client{Timeout: 5 * time.Second}

	// 1. Primary: ip-api.com with full field specification
	req1, _ := http.NewRequest("GET", "http://ip-api.com/json/?fields=status,message,country,regionName,city,district,lat,lon,isp,query", nil)
	req1.Header.Set("User-Agent", "InfoSphere-IP-Locator/2.0")
	resp1, err := client.Do(req1)
	if err == nil {
		defer resp1.Body.Close()
		var res struct {
			Status   string  `json:"status"`
			Country  string  `json:"country"`
			Region   string  `json:"regionName"`
			City     string  `json:"city"`
			District string  `json:"district"`
			Lat      float64 `json:"lat"`
			Lon      float64 `json:"lon"`
			ISP      string  `json:"isp"`
			Query    string  `json:"query"`
		}
		if json.NewDecoder(resp1.Body).Decode(&res) == nil && res.Status == "success" && res.City != "" {
			return &IPGeoResult{
				IP:        res.Query,
				City:      res.City,
				District:  res.District,
				Region:    res.Region,
				Country:   res.Country,
				Latitude:  res.Lat,
				Longitude: res.Lon,
				ISP:       res.ISP,
			}, nil
		}
	}

	// 2. Secondary: freeipapi.com (includes neighborhood / district like Gulshan)
	req2, _ := http.NewRequest("GET", "https://freeipapi.com/api/json", nil)
	req2.Header.Set("User-Agent", "InfoSphere-IP-Locator/2.0")
	resp2, err := client.Do(req2)
	if err == nil {
		defer resp2.Body.Close()
		var res struct {
			IPAddress string  `json:"ipAddress"`
			CityName  string  `json:"cityName"`
			Region    string  `json:"regionName"`
			Country   string  `json:"countryName"`
			Latitude  float64 `json:"latitude"`
			Longitude float64 `json:"longitude"`
		}
		if json.NewDecoder(resp2.Body).Decode(&res) == nil && res.IPAddress != "" && res.CityName != "" {
			return &IPGeoResult{
				IP:        res.IPAddress,
				City:      res.CityName,
				Region:    res.Region,
				Country:   res.Country,
				Latitude:  res.Latitude,
				Longitude: res.Longitude,
			}, nil
		}
	}

	// 3. Tertiary: ipwho.is
	req3, _ := http.NewRequest("GET", "https://ipwho.is/", nil)
	req3.Header.Set("User-Agent", "InfoSphere-IP-Locator/2.0")
	resp3, err := client.Do(req3)
	if err == nil {
		defer resp3.Body.Close()
		var res struct {
			Success   bool    `json:"success"`
			IP        string  `json:"ip"`
			City      string  `json:"city"`
			Region    string  `json:"region"`
			Country   string  `json:"country"`
			Latitude  float64 `json:"latitude"`
			Longitude float64 `json:"longitude"`
			Connection struct {
				ISP string `json:"isp"`
			} `json:"connection"`
		}
		if json.NewDecoder(resp3.Body).Decode(&res) == nil && res.Success && res.City != "" {
			return &IPGeoResult{
				IP:        res.IP,
				City:      res.City,
				Region:    res.Region,
				Country:   res.Country,
				Latitude:  res.Latitude,
				Longitude: res.Longitude,
				ISP:       res.Connection.ISP,
			}, nil
		}
	}

	return nil, fmt.Errorf("all dynamic IP geolocation lookups failed")
}

func formatLocation(geo *IPGeoResult) string {
	if geo == nil {
		return "Local Network"
	}
	if geo.District != "" && geo.City != "" && !strings.EqualFold(geo.District, geo.City) {
		return fmt.Sprintf("%s, %s", geo.District, geo.City)
	}
	if geo.City != "" && geo.Country != "" {
		return fmt.Sprintf("%s, %s", geo.City, geo.Country)
	}
	if geo.City != "" {
		return geo.City
	}
	if geo.Country != "" {
		return geo.Country
	}
	return "Local Network"
}

func fetchOpenMeteo(lat, lon float64, displayLoc, ipStr, ispStr string) (*WeatherData, error) {
	client := &http.Client{Timeout: 5 * time.Second}
	urlStr := fmt.Sprintf("https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,surface_pressure&timezone=auto", lat, lon)

	resp, err := client.Get(urlStr)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("open-meteo HTTP error: %d", resp.StatusCode)
	}

	var raw struct {
		Current struct {
			Temperature2m       float64 `json:"temperature_2m"`
			RelativeHumidity2m  int     `json:"relative_humidity_2m"`
			ApparentTemperature float64 `json:"apparent_temperature"`
			Precipitation       float64 `json:"precipitation"`
			WeatherCode         int     `json:"weather_code"`
			WindSpeed10m        float64 `json:"wind_speed_10m"`
			WindDirection10m    float64 `json:"wind_direction_10m"`
			SurfacePressure     float64 `json:"surface_pressure"`
		} `json:"current"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
		return nil, err
	}

	c := raw.Current
	tempC := int(math.Round(c.Temperature2m))
	tempF := int(math.Round(c.Temperature2m*9.0/5.0 + 32.0))
	feelsC := int(math.Round(c.ApparentTemperature))
	windKmph := int(math.Round(c.WindSpeed10m))
	windDir := degToCompass(c.WindDirection10m)
	condition := wmoToCondition(c.WeatherCode)
	pressure := int(math.Round(c.SurfacePressure))

	data := &WeatherData{
		Temp:       fmt.Sprintf("%d°C / %d°F", tempC, tempF),
		FeelsLike:  fmt.Sprintf("%d°C", feelsC),
		Humidity:   fmt.Sprintf("%d%%", c.RelativeHumidity2m),
		Condition:  condition,
		Wind:       fmt.Sprintf("%d km/h", windKmph),
		WindDir:    windDir,
		Visibility: "10 km",
		Pressure:   fmt.Sprintf("%d hPa", pressure),
		UVIndex:    "0",
		Location:   displayLoc,
		IP:         ipStr,
		ISP:        ispStr,
	}

	return data, nil
}

func main() {
	cityCfg := "auto"
	showWeather := true

	if cfgData, err := os.ReadFile("config.json"); err == nil {
		var config Config
		if err := json.Unmarshal(cfgData, &config); err == nil {
			if config.WeatherCity != "" {
				cityCfg = config.WeatherCity
			}
			showWeather = config.ShowWeather
		}
	}

	if !showWeather {
		fmt.Println("Weather is disabled in config.json")
		return
	}

	var lat, lon float64
	var displayLoc, ipStr, ispStr string

	cleanCity := strings.TrimSpace(cityCfg)
	isAuto := strings.ToLower(cleanCity) == "auto" || strings.ToLower(cleanCity) == "ip" || cleanCity == ""

	if isAuto {
		// DYNAMIC IP RESOLUTION: Check live public IP address and resolve location
		geo, err := geolocateByIP()
		if err == nil && geo != nil {
			lat = geo.Latitude
			lon = geo.Longitude
			displayLoc = formatLocation(geo)
			ipStr = geo.IP
			ispStr = geo.ISP
			fmt.Printf("Dynamic IP Location Resolved: %s (%s) via %s [Lat: %.4f, Lon: %.4f]\n",
				displayLoc, ipStr, ispStr, lat, lon)
		} else {
			// Fallback coordinates if offline
			lat = 23.746
			lon = 90.382
			displayLoc = "Dhaka, Bangladesh"
		}
	} else {
		// Specific city configured explicitly by user
		displayLoc = cleanCity
		// Resolve coordinates for custom city via Open-Meteo Geocoding API
		client := &http.Client{Timeout: 4 * time.Second}
		geoUrl := fmt.Sprintf("https://geocoding-api.open-meteo.com/v1/search?name=%s&count=1&language=en&format=json", url.QueryEscape(cleanCity))
		if resp, err := client.Get(geoUrl); err == nil {
			var geoRes struct {
				Results []struct {
					Latitude  float64 `json:"latitude"`
					Longitude float64 `json:"longitude"`
				} `json:"results"`
			}
			if json.NewDecoder(resp.Body).Decode(&geoRes) == nil && len(geoRes.Results) > 0 {
				lat = geoRes.Results[0].Latitude
				lon = geoRes.Results[0].Longitude
			}
			resp.Body.Close()
		}
	}

	// Fetch real-time weather from Open-Meteo for the resolved coordinates
	data, err := fetchOpenMeteo(lat, lon, displayLoc, ipStr, ispStr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error fetching weather: %v\n", err)
		os.Exit(1)
	}

	// Write weather data to output/weather.json
	_ = os.MkdirAll("output", 0755)
	outPath := filepath.Join("output", "weather.json")
	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling JSON: %v\n", err)
		os.Exit(1)
	}

	if err := os.WriteFile(outPath, jsonData, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Error writing output file: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Weather updated successfully: %s [%s] (%s) -> %s, Hum: %s, Wind: %s %s\n",
		data.Location, data.IP, data.Temp, data.Condition, data.Humidity, data.Wind, data.WindDir)
}
