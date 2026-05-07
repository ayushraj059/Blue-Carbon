// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract CarbonRegistry {
    struct CarbonCredit {
        string projectId;
        uint256 carbonTons;
        uint256 timestamp;
        bytes32 verificationHash;
        bool verificationStatus;
        address registeredBy;
    }

    mapping(string => CarbonCredit) private credits;
    string[] private projectIds;
    uint256 private totalCarbonTons;

    event CreditRegistered(
        string indexed projectId,
        uint256 carbonTons,
        address registeredBy,
        uint256 timestamp
    );

    event CreditVerified(
        string indexed projectId,
        bool status,
        uint256 timestamp
    );

    function registerCredit(
        string memory _projectId,
        uint256 _carbonTons,
        bytes32 _verificationHash
    ) external returns (bool) {
        require(bytes(_projectId).length > 0, "Project ID cannot be empty");
        require(_carbonTons > 0, "Carbon tons must be greater than zero");
        require(
            bytes(credits[_projectId].projectId).length == 0,
            "Project already registered"
        );

        credits[_projectId] = CarbonCredit({
            projectId: _projectId,
            carbonTons: _carbonTons,
            timestamp: block.timestamp,
            verificationHash: _verificationHash,
            verificationStatus: true,
            registeredBy: msg.sender
        });

        projectIds.push(_projectId);
        totalCarbonTons += _carbonTons;

        emit CreditRegistered(_projectId, _carbonTons, msg.sender, block.timestamp);
        emit CreditVerified(_projectId, true, block.timestamp);

        return true;
    }

    function getCredit(string memory _projectId)
        external
        view
        returns (
            string memory projectId,
            uint256 carbonTons,
            uint256 timestamp,
            bytes32 verificationHash,
            bool verificationStatus,
            address registeredBy
        )
    {
        CarbonCredit memory credit = credits[_projectId];
        require(bytes(credit.projectId).length > 0, "Project not found");

        return (
            credit.projectId,
            credit.carbonTons,
            credit.timestamp,
            credit.verificationHash,
            credit.verificationStatus,
            credit.registeredBy
        );
    }

    function getAllProjectIds() external view returns (string[] memory) {
        return projectIds;
    }

    function getTotalCredits() external view returns (uint256 count, uint256 totalTons) {
        return (projectIds.length, totalCarbonTons);
    }
}
