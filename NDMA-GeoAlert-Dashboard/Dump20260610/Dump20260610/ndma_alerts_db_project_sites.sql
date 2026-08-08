-- MySQL dump 10.13  Distrib 8.0.46, for Linux (x86_64)
--
-- Host: localhost    Database: ndma_alerts_db
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `project_sites`
--

DROP TABLE IF EXISTS `project_sites`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_sites` (
  `project_id` int NOT NULL,
  `project_name` varchar(100) NOT NULL,
  `lat` double DEFAULT NULL,
  `lng` double DEFAULT NULL,
  PRIMARY KEY (`project_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_sites`
--

LOCK TABLES `project_sites` WRITE;
/*!40000 ALTER TABLE `project_sites` DISABLE KEYS */;
INSERT INTO `project_sites` VALUES (1,'Bairasiul Power Station',32.809316,76.141228),(2,'Chamera III',32.47277778,76.43833333),(3,'Chutak Power Station',34.458553,76.074433),(4,'Nimmo Bazgo Power Station',34.215187,77.184514),(5,'Kishanganga Power Station',34.649019410310125,74.75174677891557),(6,'Sewa II Power Station',32.4735,75.4917),(7,'Dhauliganga Power Station',29.97833333,80.57416667),(8,'Rangit Power Station',27.29,88.29),(9,'Subansiri Lower HE Project',27.55306235,94.25867115),(10,'Parbati II HE Project',31.99833333,77.45055556),(26,'Kiru HE Project',33.346109287748824,75.95544360737556),(27,'Pakal Dul Hydro Electric Project',33.384383,75.7804902),(28,'Rangit–IV HEP',27.1599656,88.2896411),(29,'Teesta-VI HEP',27.241366,88.4744963),(30,'Tanakpur Power Station',29.05603810817019,80.11781366448484),(31,'Ratle HEP',33.1818391357182,75.80558805891253),(34,'Dulhasti Power Station',33.3,75.75),(35,'Kwar HEP',33.33,76),(36,'NHPC ICT  Test Projects',33.346109287748824,75.95544360737556),(37,'TLD-III POWER STATION',27.001,88.4427),(38,'Chamera-I',32.355,75.5909),(39,'TLD-IV POWER STATION',26.92,88.45),(41,'Uri Power Station',34.1444,74.18545),(42,'Parbati-III(Niharni)',31.778583,77.326286),(43,'Salal Ramban',33.14298612269677,74.8110663266009),(44,'Chamera II',32.47,76.25),(45,'TEESTA V POWER STATION',27.4,88.5),(46,'Sawalkote',33.2,75),(49,'Nathpa Jhakri Hydro Power Station',31.56388889,77.98027778),(50,'Sainj HEP',31.78083333,77.40972222),(51,'Rammam Hydro Power Project',27.116208237417204,88.1380464500347),(52,'NTPC KOLDAM',31.38502,76.8731),(53,'Panyor Lower',27.3425,93.8167),(54,'Kameng',27.3008,92.6225),(55,'Vyasi',30.520445,77.915214),(56,'Maneribhali-I',30.73921,78.52853),(57,'Maneribhali-II (Dharasu)',30.7294444,78.4241666),(58,'Budhil',32.2706,76.3202),(59,'Malana-II',32.1024,77.5619),(60,'Singoli Bhatwari',30.0668,79.0193),(61,'Baspa-II',31.255,78.1432),(62,'Karcham Wangtoo',31.5,78.18),(63,'Chanju-I',32.737246,76.2476251),(64,'Vishnuprayag Hydro Electric Plant',30.6725,79.51583333),(65,'Chuzachen',27.3516,88.3239),(66,'Tashiding',27.3516,88.3239),(67,'Rongnichu HEP',27.3516,88.3239),(68,'Shrinagar',30.0668,79.0193),(69,'Malana HEP Stage-1',32.1024,77.5619),(70,'BAJOLI HOLI HYDRO ELECTRIC PROJECT',32.1024,77.5619),(71,'Tapovan Vishnugad',30.0668,79.0193),(72,'Tidong-I',31.3117,78.2945),(73,'Kutehr',32.34940833,76.53150833),(75,'Integrated Kashang',32.1024,77.5619),(76,'Vishnugad Pipalkoti Hydro Electric Project',30.3049,79.293),(77,'Naitwar Mori Hydro Power Station',31.063165,78.097473),(78,'Allain Duhangan',32.1024,77.5619),(79,'Sorang',31.354,77.5238),(80,'Dikchu',32.1024,77.5619),(81,'Sawra Kuddu',31.13,77.75),(82,'Shongtong-Karchham Hydro Electric Project( 450MW)',32.1024,77.5619),(83,'Shanan',31.9894,76.8072),(84,'Teesta III',27.3516,88.3239),(85,'Sanjay (Bhaba)',32.1024,77.5619),(86,'Upper Sindh-II',33.2778,75.3412),(91,'URI-II POWER STATION',34.0921,74.0318),(92,'Tehri Dam & HPP (Stage-I)',30.3777624,78.1754065),(93,'Koteshwar HEP',30.2620001,78.4913277),(96,'Luhri Hydro Electric Project Stage-1',31.362080596903844,77.53652170721269),(97,'Dhaulasidh HEP',31.8064167,76.4418608);
/*!40000 ALTER TABLE `project_sites` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-06-10 10:45:17
