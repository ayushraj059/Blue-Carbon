const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const network = hre.network.name;
  console.log(`Deploying CarbonRegistry to network: ${network}`);

  const [deployer] = await ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log("Account balance:", ethers.formatEther(balance), "MATIC");

  const CarbonRegistry = await ethers.getContractFactory("CarbonRegistry");
  const contract = await CarbonRegistry.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("CarbonRegistry deployed to:", address);

  // Save deployed address
  const deployedData = {
    address,
    network: hre.network.name,
    deployer: deployer.address,
    deployedAt: new Date().toISOString(),
  };

  const outputPath = path.join(__dirname, "../deployed_address.json");
  fs.writeFileSync(outputPath, JSON.stringify(deployedData, null, 2));
  console.log("Contract address saved to:", outputPath);

  // Also copy ABI to backend location
  const artifactPath = path.join(
    __dirname,
    "../artifacts/CarbonRegistry.sol/CarbonRegistry.json"
  );

  if (fs.existsSync(artifactPath)) {
    const backendAbiDir = path.join(__dirname, "../../backend/blockchain");
    if (!fs.existsSync(backendAbiDir)) {
      fs.mkdirSync(backendAbiDir, { recursive: true });
    }
    const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
    fs.writeFileSync(
      path.join(backendAbiDir, "CarbonRegistry_abi.json"),
      JSON.stringify(artifact.abi, null, 2)
    );
    console.log("ABI copied to backend/blockchain/CarbonRegistry_abi.json");
  }

  console.log("\nDeployment complete!");
  console.log("Add this to your .env file:");
  console.log(`CONTRACT_ADDRESS=${address}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
