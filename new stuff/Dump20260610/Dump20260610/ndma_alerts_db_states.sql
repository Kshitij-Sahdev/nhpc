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
-- Table structure for table `states`
--

DROP TABLE IF EXISTS `states`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `states` (
  `state_id` int NOT NULL AUTO_INCREMENT,
  `state_name` varchar(100) NOT NULL,
  `feed_slug` varchar(100) NOT NULL,
  `is_selected` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`state_id`),
  UNIQUE KEY `state_name` (`state_name`),
  UNIQUE KEY `feed_slug` (`feed_slug`)
) ENGINE=InnoDB AUTO_INCREMENT=36 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `states`
--

LOCK TABLES `states` WRITE;
/*!40000 ALTER TABLE `states` DISABLE KEYS */;
INSERT INTO `states` VALUES (1,'Andaman & Nicobar Islands','andaman',0),(2,'Andhra Pradesh','andhra',0),(3,'Arunachal Pradesh','arunachal',0),(4,'Assam','assam',1),(5,'Bihar','bihar',0),(6,'Chandigarh','chandigarh',0),(7,'Chhattisgarh','chhattisgarh',0),(8,'Dadra & Nagar Haveli and Daman & Diu','dadra',0),(9,'Delhi','delhi',1),(10,'Goa','goa',0),(11,'Gujarat','gujarat',0),(12,'Haryana','haryana',1),(13,'Himachal Pradesh','himachal',0),(14,'Jammu & Kashmir','jammu',1),(15,'Karnataka','karnataka',0),(16,'Kerala','kerala',0),(17,'Ladakh','ladakh',0),(18,'Lakshadweep','lakshadweep',0),(19,'Madhya Pradesh','madhya',0),(20,'Maharashtra','maharashtra',0),(21,'Manipur','manipur',0),(22,'Meghalaya','meghalaya',1),(23,'Mizoram','mizoram',0),(24,'Nagaland','nagaland',0),(25,'Odisha','odisha',0),(26,'Puducherry','puducherry',0),(27,'Punjab','punjab',0),(28,'Rajasthan','rajasthan',0),(29,'Sikkim','sikkim',1),(30,'Tamil Nadu','tamil',0),(31,'Telangana','telangana',0),(32,'Tripura','tripura',0),(33,'Uttarakhand','uttarakhand',1),(34,'Uttar Pradesh','uttar',1),(35,'West Bengal','west',0);
/*!40000 ALTER TABLE `states` ENABLE KEYS */;
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
