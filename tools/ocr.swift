import Foundation
import Vision
import CoreImage

guard CommandLine.arguments.count > 1 else {
    fputs("Usage: ocr.swift <image-path>\n", stderr)
    exit(1)
}

let imagePath = CommandLine.arguments[1]
let fileURL = URL(fileURLWithPath: imagePath)

guard let ciImage = CIImage(contentsOf: fileURL) else {
    fputs("Error: Could not load image from \(imagePath)\n", stderr)
    exit(1)
}

let request = VNRecognizeTextRequest { (request, error) in
    if let error = error {
        fputs("Recognition error: \(error.localizedDescription)\n", stderr)
        return
    }
    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        return
    }
    for observation in observations {
        if let topCandidate = observation.topCandidates(1).first {
            print(topCandidate.string)
        }
    }
}

request.recognitionLevel = .accurate
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(ciImage: ciImage, options: [:])
do {
    try handler.perform([request])
} catch {
    fputs("Handler error: \(error.localizedDescription)\n", stderr)
    exit(1)
}
