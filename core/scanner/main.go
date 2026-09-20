package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"os/exec"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

// NetworkClient represents a discovered network device
type NetworkClient struct {
	Name           string  `json:"name"`
	IP             string  `json:"ip"`
	MAC            string  `json:"mac"`
	Band           string  `json:"band"`
	RSSI           int     `json:"rssi"`
	TxMB           float64 `json:"tx_mb"`
	RxMB           float64 `json:"rx_mb"`
	LatencyMS      float64 `json:"latency_ms"`
	HostnameSource string  `json:"hostname_source"`
}

var (
	vendors = map[string]string{
		"38-D5-7A": "Dell",
		"50-91-E3": "Reecam",
		"74-33-57": "Huawei",
		"BC-7F-A4": "Samsung",
		"D8-CE-3A": "Xiaomi",
		"A4-5E-60": "Xiaomi",
		"AC-DE-48": "Apple",
		"3C-5A-B4": "Google",
		"CC-47-40": "Apple",
		"B0-A4-60": "TP-Link",
		"8C-F5-A3": "Xiaomi",
		"44-6A-2E": "Apple",
		"DC-A6-32": "RPi",
		"B8-27-EB": "RPi",
		"00-50-56": "VMware",
		"08-00-27": "VBox",
		"52-54-00": "QEMU",
		"18-31-BF": "Amazon",
		"FC-65-DE": "Xiaomi",
		"64-B5-C6": "Xiaomi",
		"34-CE-00": "Xiaomi",
		"7C-F1-7E": "TP-Link",
		"C4-B3-01": "Apple",
		"7E-52-E4": "Android",
	}

	localOverrides = map[string]string{}
)

func getSubnetAndIPs() (string, []string, string, error) {
	// Find preferred local IP (non-loopback, active)
	conn, err := net.Dial("udp", "8.8.8.8:80")
	if err != nil {
		return "", nil, "", err
	}
	defer conn.Close()

	localAddr := conn.LocalAddr().(*net.UDPAddr)
	localIP := localAddr.IP.String()
	parts := strings.Split(localIP, ".")
	if len(parts) != 4 {
		return "", nil, "", fmt.Errorf("unexpected local IP format: %s", localIP)
	}

	subnetPrefix := fmt.Sprintf("%s.%s.%s.", parts[0], parts[1], parts[2])

	var ips []string
	for i := 1; i <= 254; i++ {
		ip := fmt.Sprintf("%s%d", subnetPrefix, i)
		ips = append(ips, ip)
	}

	return subnetPrefix, ips, localIP, nil
}

// NetBIOS Name Query packet (UDP 137)
func getNetBIOSName(ip string) string {
	d := net.Dialer{Timeout: 150 * time.Millisecond}
	conn, err := d.Dial("udp", ip+":137")
	if err != nil {
		return ""
	}
	defer conn.Close()

	// Transaction ID: 0x1234, Flags: 0x0000 (Query), Questions: 1
	// Question Name: CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA (encoded "*" representing node status)
	// Type: NBSTAT (0x0021), Class: IN (0x0001)
	query := []byte{
		0x12, 0x34, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00, 0x20, 0x43, 0x4b, 0x41,
		0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41,
		0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41,
		0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41,
		0x41, 0x41, 0x41, 0x41, 0x41, 0x00, 0x00, 0x21,
		0x00, 0x01,
	}

	_, err = conn.Write(query)
	if err != nil {
		return ""
	}

	buf := make([]byte, 1024)
	_ = conn.SetReadDeadline(time.Now().Add(150 * time.Millisecond))
	n, err := conn.Read(buf)
	if err != nil || n < 57 {
		return ""
	}

	// Parse NetBIOS response
	// Number of names is at offset 56
	numNames := int(buf[56])
	offset := 57
	for i := 0; i < numNames; i++ {
		if offset+18 > n {
			break
		}
		nameBytes := buf[offset : offset+15]
		nameType := buf[offset+15]
		// nameType 0x00 is Workstation Service (computer name)
		if nameType == 0x00 {
			name := strings.TrimSpace(string(nameBytes))
			if len(name) > 0 {
				return name
			}
		}
		offset += 18 // each name entry is 18 bytes
	}
	return ""
}

// Minimal mDNS lookup (UDP 5353)
func getmDNSName(ip string) string {
	// Let's send a unicast mDNS query to UDP 5353 of the device
	d := net.Dialer{Timeout: 150 * time.Millisecond}
	conn, err := d.Dial("udp", ip+":5353")
	if err != nil {
		return ""
	}
	defer conn.Close()

	// Reverse IP pointer query for PTR record: e.g. "x.x.x.x.in-addr.arpa"
	octets := strings.Split(ip, ".")
	if len(octets) != 4 {
		return ""
	}
	revIP := fmt.Sprintf("%s.%s.%s.%s.in-addr.arpa", octets[3], octets[2], octets[1], octets[0])

	// Header: ID: 0x0001, Flags: 0x0100 (Standard Query), QDCOUNT: 1
	var packet bytes.Buffer
	packet.Write([]byte{0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00})
	for _, label := range strings.Split(revIP, ".") {
		packet.WriteByte(byte(len(label)))
		packet.WriteString(label)
	}
	packet.WriteByte(0x00) // End label
	packet.Write([]byte{0x00, 0x0c, 0x00, 0x01}) // QTYPE: PTR (12), QCLASS: IN (1)

	_, err = conn.Write(packet.Bytes())
	if err != nil {
		return ""
	}

	buf := make([]byte, 1024)
	_ = conn.SetReadDeadline(time.Now().Add(150 * time.Millisecond))
	n, err := conn.Read(buf)
	if err != nil || n < 12 {
		return ""
	}

	// Parse PTR response. Look for domain name starting with length byte.
	// Check answer section. ANCOUNT at offset 6, 7
	ancount := binary.BigEndian.Uint16(buf[6:8])
	if ancount == 0 {
		return ""
	}

	// Skip header and question section
	pos := 12
	// Skip question name labels
	for pos < n {
		length := int(buf[pos])
		if length == 0 {
			pos++
			break
		}
		if length&0xC0 == 0xC0 {
			pos += 2
			break
		}
		pos += length + 1
	}
	pos += 4 // Skip QTYPE + QCLASS

	// Read answer name (could be compressed)
	if pos < n {
		if buf[pos]&0xC0 == 0xC0 {
			pos += 2
		} else {
			for pos < n {
				l := int(buf[pos])
				if l == 0 {
					pos++
					break
				}
				pos += l + 1
			}
		}
	}
	pos += 10 // skip TYPE(2) + CLASS(2) + TTL(4) + RDLENGTH(2)

	// Now read the actual domain name inside the RDATA PTR
	if pos < n {
		var parts []string
		visited := make(map[int]bool)
		curr := pos
		for curr < n {
			l := int(buf[curr])
			if l == 0 {
				break
			}
			if l&0xC0 == 0xC0 {
				if curr+1 >= n {
					break
				}
				ptr := int(l&0x3F)<<8 | int(buf[curr+1])
				if visited[ptr] {
					break
				}
				visited[ptr] = true
				curr = ptr
				continue
			}
			curr++
			if curr+l > n {
				break
			}
			parts = append(parts, string(buf[curr:curr+l]))
			curr += l
		}
		if len(parts) > 0 {
			fullName := strings.Join(parts, ".")
			return strings.TrimSuffix(fullName, ".")
		}
	}

	return ""
}

// Reverse DNS Lookup
func getReverseDNS(ip string, gatewayIP string) string {
	d := net.Resolver{
		PreferGo: true,
		Dial: func(ctx context.Context, network, address string) (net.Conn, error) {
			var dialer net.Dialer
			return dialer.DialContext(ctx, "udp", gatewayIP+":53")
		},
	}
	ctx, cancel := context.WithTimeout(context.Background(), 80*time.Millisecond)
	defer cancel()

	names, err := d.LookupAddr(ctx, ip)
	if err == nil && len(names) > 0 {
		name := strings.Split(names[0], ".")[0]
		if len(name) > 0 && name != ip {
			return name
		}
	}
	return ""
}

type MIB_IPNETROW struct {
	Index       uint32
	PhysAddrLen uint32
	PhysAddr    [8]byte
	Addr        uint32
	Type        uint32
}

// Parse system ARP table output using native Win32 GetIpNetTable (0 subprocesses)
func getARPTable() map[string]string {
	arpMap := make(map[string]string)
	if runtime.GOOS == "windows" {
		iphlpapi := syscall.NewLazyDLL("iphlpapi.dll")
		procGetIpNetTable := iphlpapi.NewProc("GetIpNetTable")

		var size uint32 = 0
		procGetIpNetTable.Call(0, uintptr(unsafe.Pointer(&size)), 0)
		if size == 0 {
			return arpMap
		}

		buf := make([]byte, size)
		ret, _, _ := procGetIpNetTable.Call(uintptr(unsafe.Pointer(&buf[0])), uintptr(unsafe.Pointer(&size)), 0)
		if ret != 0 {
			return arpMap
		}

		numEntries := *(*uint32)(unsafe.Pointer(&buf[0]))
		rowSize := unsafe.Sizeof(MIB_IPNETROW{})
		dataPtr := uintptr(unsafe.Pointer(&buf[4]))

		for i := uint32(0); i < numEntries; i++ {
			row := (*MIB_IPNETROW)(unsafe.Pointer(dataPtr + uintptr(i)*rowSize))
			if row.PhysAddrLen == 6 {
				ip := net.IPv4(byte(row.Addr), byte(row.Addr>>8), byte(row.Addr>>16), byte(row.Addr>>24)).String()
				mac := fmt.Sprintf("%02X:%02X:%02X:%02X:%02X:%02X",
					row.PhysAddr[0], row.PhysAddr[1], row.PhysAddr[2],
					row.PhysAddr[3], row.PhysAddr[4], row.PhysAddr[5])
				if !isBroadcastMAC(mac) {
					arpMap[ip] = mac
				}
			}
		}
		return arpMap
	}

	cmd := exec.Command("arp", "-a")
	output, err := cmd.Output()
	if err != nil {
		return arpMap
	}

	re := regexp.MustCompile(`(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}[:-](?:[0-9a-fA-F]{2}[:-]){4}[0-9a-fA-F]{2})`)
	matches := re.FindAllStringSubmatch(string(output), -1)
	for _, match := range matches {
		ip := match[1]
		mac := formatMAC(match[2])
		if !isBroadcastMAC(mac) {
			arpMap[ip] = mac
		}
	}
	return arpMap
}

func formatMAC(raw string) string {
	clean := strings.Map(func(r rune) rune {
		if (r >= '0' && r <= '9') || (r >= 'a' && r <= 'f') || (r >= 'A' && r <= 'F') {
			return r
		}
		return -1
	}, raw)
	if len(clean) != 12 {
		return strings.ToUpper(raw)
	}
	var parts []string
	for i := 0; i < 12; i += 2 {
		parts = append(parts, strings.ToUpper(clean[i:i+2]))
	}
	return strings.Join(parts, ":")
}

func isBroadcastMAC(mac string) bool {
	m := strings.ReplaceAll(mac, ":", "")
	return m == "FFFFFFFFFFFF" || m == "000000000000" || m == ""
}

func getVendor(mac string) string {
	if mac == "SELF" {
		return "Local"
	}
	parts := strings.Split(mac, ":")
	if len(parts) >= 3 {
		prefix := strings.ToUpper(fmt.Sprintf("%s-%s-%s", parts[0], parts[1], parts[2]))
		if vendor, ok := vendors[prefix]; ok {
			return vendor
		}
	}
	return ""
}

func probeIP(ip string, localIP string, gatewayIP string) *NetworkClient {
	// Determine latency by dial connection to common TCP ports (extremely fast)
	ports := []int{80, 135, 445}
	alive := false
	var latency time.Duration

	t0 := time.Now()
	for _, port := range ports {
		address := net.JoinHostPort(ip, strconv.Itoa(port))
		conn, err := net.DialTimeout("tcp", address, 50*time.Millisecond)
		if err == nil {
			conn.Close()
			latency = time.Since(t0)
			alive = true
			break
		}
	}

	// Even if TCP ports are closed, let's query UDP ports (NetBIOS or mDNS) which also wakes up the host
	var name string
	var source string

	if !alive {
		// Try UDP NetBIOS query
		if n := getNetBIOSName(ip); n != "" {
			name = n
			source = "netbios"
			alive = true
		}
	} else {
		if n := getNetBIOSName(ip); n != "" {
			name = n
			source = "netbios"
		}
	}

	if name == "" {
		if m := getmDNSName(ip); m != "" {
			name = m
			source = "mdns"
			alive = true
		}
	}

	if name == "" {
		if dns := getReverseDNS(ip, gatewayIP); dns != "" {
			name = dns
			source = "dns"
		}
	}

	if !alive {
		return nil
	}

	// Construct basic client details
	client := &NetworkClient{
		IP:             ip,
		LatencyMS:      float64(latency.Nanoseconds()) / 1e6,
		Name:           name,
		HostnameSource: source,
		RSSI:           80, // Default signal strength
		Band:           "WLAN",
	}

	if ip == gatewayIP {
		client.Band = "Wired"
		client.RSSI = 100
	}

	return client
}

func main() {
	subnetPrefix, ips, localIP, err := getSubnetAndIPs()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error getting local subnet: %v\n", err)
		os.Exit(1)
	}

	gatewayIP := subnetPrefix + "1" // Standard router gateway IP

	// Query ARP table first to populate known devices
	initialARP := getARPTable()

	// Concurrent scan of the subnet
	var wg sync.WaitGroup
	var mu sync.Mutex
	discovered := make(map[string]*NetworkClient)

	sem := make(chan struct{}, 80) // limit concurrency to be friendly to resources

	for _, ip := range ips {
		if ip == localIP {
			continue // Skip self in the active probe, added separately later
		}
		wg.Add(1)
		go func(targetIP string) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()

			client := probeIP(targetIP, localIP, gatewayIP)
			if client != nil {
				mu.Lock()
				discovered[targetIP] = client
				mu.Unlock()
			}
		}(ip)
	}

	wg.Wait()

	// Fetch updated ARP table (the probes will have populated it dynamically)
	finalARP := getARPTable()

	// Combine discovered devices with ARP information
	var clients []NetworkClient
	mergedIPs := make(map[string]bool)

	// First, include all probed active devices
	for ip, client := range discovered {
		mac := finalARP[ip]
		if mac == "" {
			mac = initialARP[ip] // fallback to initial
		}
		client.MAC = mac
		
		// Fill name if still missing
		if client.Name == "" {
			if overrideName, exists := localOverrides[mac]; exists {
				client.Name = overrideName
				client.HostnameSource = "local"
			} else {
				vendorName := getVendor(mac)
				parts := strings.Split(ip, ".")
				lastOctet := parts[len(parts)-1]
				if vendorName != "" {
					client.Name = fmt.Sprintf("%s_%s", vendorName, lastOctet)
					client.HostnameSource = "vendor"
				} else {
					client.Name = fmt.Sprintf("Device_%s", lastOctet)
					client.HostnameSource = "synthetic"
				}
			}
		}

		// Check if it's the gateway
		if ip == gatewayIP {
			client.Band = "Wired"
			client.RSSI = 100
		} else {
			// Band classification heuristic:
			lowerName := strings.ToLower(client.Name)
			if strings.Contains(lowerName, "tv") || strings.Contains(lowerName, "camera") || strings.Contains(lowerName, "printer") {
				client.Band = "2.4 GHz"
			} else if strings.Contains(lowerName, "iphone") || strings.Contains(lowerName, "macbook") || strings.Contains(lowerName, "phone") {
				client.Band = "5 GHz"
				client.RSSI = 85
			} else {
				client.Band = "2.4 GHz"
			}
		}

		clients = append(clients, *client)
		mergedIPs[ip] = true
	}

	// Also add any devices in ARP table that we might have missed in the probe (e.g. silent devices or UDP-only)
	for ip, mac := range finalARP {
		if mergedIPs[ip] || ip == localIP || !strings.HasPrefix(ip, subnetPrefix) {
			continue
		}

		parts := strings.Split(ip, ".")
		lastOctet := parts[len(parts)-1]
		name := ""
		source := "arp"

		if overrideName, exists := localOverrides[mac]; exists {
			name = overrideName
			source = "local"
		} else {
			vendorName := getVendor(mac)
			if vendorName != "" {
				name = fmt.Sprintf("%s_%s", vendorName, lastOctet)
				source = "vendor"
			} else {
				name = fmt.Sprintf("Device_%s", lastOctet)
				source = "synthetic"
			}
		}

		band := "2.4 GHz"
		if ip == gatewayIP {
			band = "Wired"
		}

		clients = append(clients, NetworkClient{
			Name:           name,
			IP:             ip,
			MAC:            mac,
			Band:           band,
			RSSI:           70,
			TxMB:           0.0,
			RxMB:           0.0,
			LatencyMS:      5.0,
			HostnameSource: source,
		})
	}

	// Format output to JSON and print to stdout
	jsonData, err := json.MarshalIndent(clients, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(jsonData))
}
