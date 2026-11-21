// Horizon tilt of a picture (macOS Vision VNDetectHorizonRequest). Image paths one per line on stdin.
// Prints the angle in degrees per image (+ = the picture is turned clockwise, so it needs turning back by -angle),
// or "none" when Vision sees no horizon (a close-up, a wall, a face).
import Foundation
import Vision
import AppKit

while let path = readLine() {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("none"); continue }
    let req = VNDetectHorizonRequest()
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    if let h = req.results?.first { print(String(format: "%.2f", Double(h.angle) * 180 / Double.pi)) } else { print("none") }
}
