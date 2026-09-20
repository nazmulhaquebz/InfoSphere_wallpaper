package main

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/jpeg"
	_ "image/png"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Bilinear image resizing algorithm to keep the build fully self-contained
func resizeBilinear(img image.Image, width, height int) image.Image {
	bounds := img.Bounds()
	dx := bounds.Dx()
	dy := bounds.Dy()

	dst := image.NewRGBA(image.Rect(0, 0, width, height))

	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			srcX := float64(x) * float64(dx) / float64(width)
			srcY := float64(y) * float64(dy) / float64(height)

			x0 := int(srcX)
			y0 := int(srcY)
			x1 := x0 + 1
			if x1 >= dx {
				x1 = dx - 1
			}
			y1 := y0 + 1
			if y1 >= dy {
				y1 = dy - 1
			}

			fx := srcX - float64(x0)
			fy := srcY - float64(y0)

			c00 := img.At(bounds.Min.X+x0, bounds.Min.Y+y0)
			c10 := img.At(bounds.Min.X+x1, bounds.Min.Y+y0)
			c01 := img.At(bounds.Min.X+x0, bounds.Min.Y+y1)
			c11 := img.At(bounds.Min.X+x1, bounds.Min.Y+y1)

			r00, g00, b00, a00 := c00.RGBA()
			r10, g10, b10, a10 := c10.RGBA()
			r01, g01, b01, a01 := c01.RGBA()
			r11, g11, b11, a11 := c11.RGBA()

			// Bilinear interpolation
			r := float64(r00)*(1-fx)*(1-fy) + float64(r10)*fx*(1-fy) + float64(r01)*(1-fx)*fy + float64(r11)*fx*fy
			g := float64(g00)*(1-fx)*(1-fy) + float64(g10)*fx*(1-fy) + float64(g01)*(1-fx)*fy + float64(g11)*fx*fy
			b := float64(b00)*(1-fx)*(1-fy) + float64(b10)*fx*(1-fy) + float64(b01)*(1-fx)*fy + float64(b11)*fx*fy
			a := float64(a00)*(1-fx)*(1-fy) + float64(a10)*fx*(1-fy) + float64(a01)*(1-fx)*fy + float64(a11)*fx*fy

			dst.Set(x, y, color.RGBA{
				R: uint8(r / 257),
				G: uint8(g / 257),
				B: uint8(b / 257),
				A: uint8(a / 257),
			})
		}
	}

	return dst
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	return err
}

func main() {
	pictureDir := "Picture"
	cacheDir := filepath.Join(pictureDir, "cache")
	outputDir := "output"

	_ = os.MkdirAll(cacheDir, 0755)
	_ = os.MkdirAll(outputDir, 0755)

	// Step 1: Scan for original image files
	files, err := os.ReadDir(pictureDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error scanning Picture folder: %v\n", err)
		os.Exit(1)
	}

	var imageFiles []string
	for _, f := range files {
		if f.IsDir() {
			continue
		}
		ext := strings.ToLower(filepath.Ext(f.Name()))
		if ext == ".jpg" || ext == ".jpeg" || ext == ".png" {
			imageFiles = append(imageFiles, f.Name())
		}
	}

	if len(imageFiles) == 0 {
		fmt.Println("No images found in Picture directory.")
		return
	}

	// Step 2: Validate and compress each original file to under 100 KB
	for _, name := range imageFiles {
		srcPath := filepath.Join(pictureDir, name)
		cachePath := filepath.Join(cacheDir, strings.TrimSuffix(name, filepath.Ext(name))+".jpg")

		srcInfo, err := os.Stat(srcPath)
		if err != nil {
			continue
		}

		cacheInfo, err := os.Stat(cachePath)
		needCompress := false
		if err != nil || os.IsNotExist(err) {
			needCompress = true
		} else if srcInfo.ModTime().After(cacheInfo.ModTime()) {
			needCompress = true
		}

		if needCompress {
			func() {
				file, err := os.Open(srcPath)
				if err != nil {
					return
				}
				defer file.Close()

				orientation := 1
				ext := strings.ToLower(filepath.Ext(srcPath))
				if ext == ".jpg" || ext == ".jpeg" {
					orientation = readEXIFOrientation(file)
					_, _ = file.Seek(0, 0)
				}

				img, _, err := image.Decode(file)
				if err != nil {
					return
				}

				img = applyOrientation(img, orientation)

				// Resize to HD proportions (max dimension 1024) to keep it crisp and HD formatted
				bounds := img.Bounds()
				aspectRatio := float64(bounds.Dx()) / float64(bounds.Dy())
				width := 1024
				height := int(1024.0 / aspectRatio)
				if height > 1024 {
					height = 1024
					width = int(1024.0 * aspectRatio)
				}

				resizedImg := resizeBilinear(img, width, height)

				// Encode with quality adjustment to ensure size is strictly under 100 KB
				quality := 75
				for {
					outFile, err := os.Create(cachePath)
					if err != nil {
						return
					}
					opt := jpeg.Options{Quality: quality}
					err = jpeg.Encode(outFile, resizedImg, &opt)
					outFile.Close()
					if err != nil {
						return
					}

					// Check file size
					fi, err := os.Stat(cachePath)
					if err == nil && fi.Size() < 100*1024 {
						break // Success, under 100 KB
					}

					// If size >= 100 KB, lower the quality and try again
					quality -= 10
					if quality < 15 {
						break // Fallback, don't loop forever
					}
				}
			}()
		}
	}

	// Step 3: Find all files in the cache directory
	cacheFiles, err := os.ReadDir(cacheDir)
	if err != nil || len(cacheFiles) == 0 {
		fmt.Println("Cache is empty.")
		return
	}

	var cachedImages []string
	for _, f := range cacheFiles {
		if !f.IsDir() && filepath.Ext(f.Name()) == ".jpg" {
			cachedImages = append(cachedImages, f.Name())
		}
	}

	// Step 4: Rotate active image based on time (rotates every 10 seconds)
	rotationSecs := int64(10)
	index := int((time.Now().Unix() / rotationSecs) % int64(len(cachedImages)))
	activeCacheName := cachedImages[index]
	activeCachePath := filepath.Join(cacheDir, activeCacheName)
	activeOutPath := filepath.Join(outputDir, "cam_feed_active.jpg")

	err = copyFile(activeCachePath, activeOutPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error copying active file: %v\n", err)
		os.Exit(1)
	}

	// Step 5: Write status JSON for the Node/Next.js dashboard
	activeOutInfo, _ := os.Stat(activeOutPath)
	statusPath := filepath.Join(outputDir, "cam_feed_status.json")
	statusData := map[string]interface{}{
		"active_file": activeCacheName,
		"size_kb":     float64(activeOutInfo.Size()) / 1024.0,
		"timestamp":   time.Now().Unix(),
	}

	statusJSON, _ := json.MarshalIndent(statusData, "", "  ")
	_ = os.WriteFile(statusPath, statusJSON, 0644)

	fmt.Printf("Active dynamic picture updated: %s (%.2f KB)\n", activeCacheName, float64(activeOutInfo.Size())/1024.0)
}

// ReadEXIFOrientation reads EXIF orientation tag from a JPEG reader.
// Returns orientation value (1-8), or 1 if not found or error.
func readEXIFOrientation(r io.ReadSeeker) int {
	var header [2]byte
	if _, err := io.ReadFull(r, header[:]); err != nil || header[0] != 0xff || header[1] != 0xd8 {
		return 1
	}

	var buf [4]byte
	for {
		if _, err := io.ReadFull(r, buf[:2]); err != nil {
			break
		}
		if buf[0] != 0xff {
			break
		}
		marker := buf[1]
		if marker == 0xda || marker == 0xd9 { // SOS or EOI
			break
		}

		if _, err := io.ReadFull(r, buf[2:4]); err != nil {
			break
		}
		length := int(binary.BigEndian.Uint16(buf[2:4])) - 2
		if length < 0 {
			break
		}

		if marker == 0xe1 { // APP1 EXIF
			exifHeader := make([]byte, 6)
			if _, err := io.ReadFull(r, exifHeader); err != nil {
				break
			}
			length -= 6
			if string(exifHeader[:4]) == "Exif" && exifHeader[4] == 0 && exifHeader[5] == 0 {
				tiffData := make([]byte, length)
				if _, err := io.ReadFull(r, tiffData); err != nil {
					break
				}
				return parseTiffOrientation(tiffData)
			}
		}

		// Skip marker payload
		if _, err := r.Seek(int64(length), io.SeekCurrent); err != nil {
			break
		}
	}
	return 1
}

func parseTiffOrientation(data []byte) int {
	if len(data) < 8 {
		return 1
	}
	var order binary.ByteOrder
	if data[0] == 'I' && data[1] == 'I' {
		order = binary.LittleEndian
	} else if data[0] == 'M' && data[1] == 'M' {
		order = binary.BigEndian
	} else {
		return 1
	}

	if order.Uint16(data[2:4]) != 42 {
		return 1
	}

	ifdOffset := int(order.Uint32(data[4:8]))
	if ifdOffset < 8 || ifdOffset >= len(data) {
		return 1
	}

	if ifdOffset+2 > len(data) {
		return 1
	}
	numEntries := int(order.Uint16(data[ifdOffset : ifdOffset+2]))
	entryOffset := ifdOffset + 2

	for i := 0; i < numEntries; i++ {
		if entryOffset+12 > len(data) {
			break
		}
		tag := order.Uint16(data[entryOffset : entryOffset+2])
		if tag == 0x0112 {
			dataType := order.Uint16(data[entryOffset+2 : entryOffset+4])
			if dataType == 3 {
				return int(order.Uint16(data[entryOffset+8 : entryOffset+10]))
			}
		}
		entryOffset += 12
	}
	return 1
}

func rotate90(img image.Image) image.Image {
	bounds := img.Bounds()
	w, h := bounds.Dx(), bounds.Dy()
	dst := image.NewRGBA(image.Rect(0, 0, h, w))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			dst.Set(h-1-y, x, img.At(bounds.Min.X+x, bounds.Min.Y+y))
		}
	}
	return dst
}

func rotate180(img image.Image) image.Image {
	bounds := img.Bounds()
	w, h := bounds.Dx(), bounds.Dy()
	dst := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			dst.Set(w-1-x, h-1-y, img.At(bounds.Min.X+x, bounds.Min.Y+y))
		}
	}
	return dst
}

func rotate270(img image.Image) image.Image {
	bounds := img.Bounds()
	w, h := bounds.Dx(), bounds.Dy()
	dst := image.NewRGBA(image.Rect(0, 0, h, w))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			dst.Set(y, w-1-x, img.At(bounds.Min.X+x, bounds.Min.Y+y))
		}
	}
	return dst
}

func flipHorizontal(img image.Image) image.Image {
	bounds := img.Bounds()
	w, h := bounds.Dx(), bounds.Dy()
	dst := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			dst.Set(w-1-x, y, img.At(bounds.Min.X+x, bounds.Min.Y+y))
		}
	}
	return dst
}

func applyOrientation(img image.Image, orientation int) image.Image {
	switch orientation {
	case 2:
		return flipHorizontal(img)
	case 3:
		return rotate180(img)
	case 4:
		return rotate180(flipHorizontal(img))
	case 5:
		return rotate270(flipHorizontal(img))
	case 6:
		return rotate90(img)
	case 7:
		return rotate90(flipHorizontal(img))
	case 8:
		return rotate270(img)
	default:
		return img
	}
}
