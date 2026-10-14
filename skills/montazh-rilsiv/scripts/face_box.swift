// Prints one line per image: x y w h of the largest face, normalised 0..1 with y from the TOP (or "none").
import Foundation
import Vision
import AppKit
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("none"); continue }
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    guard let f = (req.results ?? []).max(by: { $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height }) else { print("none"); continue }
    let b = f.boundingBox
    print(String(format: "%.4f %.4f %.4f %.4f", b.minX, 1 - b.maxY, b.width, b.height))
}
