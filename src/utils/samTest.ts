import {
  initSegmentation,
  createSession,
  precomputeEmbedding,
} from "minisam";

export async function testSamSegmentation(imageElement: HTMLImageElement) {
  try {
    console.log("Initializing SAM segmentation...");
    await initSegmentation();
    console.log("SAM initialization complete.");

    console.log("Precomputing image embedding...");
    await precomputeEmbedding(imageElement);
    console.log("Image embedding complete.");

    console.log("Creating segmentation session...");
    const session = createSession(imageElement);
    console.log("Session created.");

    // Add a sample click in the center of the image
    const centerX = imageElement.width / 2;
    const centerY = imageElement.height / 2;
    // 添加正点击（包含区域）
    session.addClick(centerX, centerY, "include");
    console.log("Added positive click at center.");

    console.log("Performing segmentation...");
    const imageDataMask = await session.segment(imageElement);
    console.log("Segmentation complete.");

    // Clean up
    session.dispose();

    return imageDataMask;
  } catch (error) {
    console.error("Error during SAM segmentation:", error);
    throw error;
  }
}